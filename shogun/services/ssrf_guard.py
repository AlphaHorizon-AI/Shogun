"""Policy-based validation for user-controlled outbound HTTP destinations.

The guard deliberately validates every resolved address.  Callers must keep
redirect following disabled so a validated URL cannot redirect to a different
destination without another policy decision.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import socket
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from urllib.parse import urlsplit, urlunsplit

logger = logging.getLogger(__name__)


class SSRFValidationError(ValueError):
    """Raised when an outbound URL violates its destination policy."""

    def __init__(self, message: str, *, reason: str, host: str | None = None) -> None:
        super().__init__(message)
        self.reason = reason
        self.host = host


class OutboundDestinationPolicy(str, Enum):
    PUBLIC_ONLY = "public_only"
    PRIVATE_ALLOWED = "private_allowed"
    LOOPBACK_ALLOWED = "loopback_allowed"
    LOOPBACK_ONLY = "loopback_only"
    ALLOWLIST_ONLY = "allowlist_only"


@dataclass(frozen=True)
class ValidatedDestination:
    url: str
    scheme: str
    host: str
    port: int
    addresses: tuple[ipaddress.IPv4Address | ipaddress.IPv6Address, ...]

    @property
    def pinned_url(self) -> str:
        """Return the URL with its authority pinned to a validated address."""

        parsed = urlsplit(self.url)
        address = str(self.addresses[0])
        literal = f"[{address}]" if ":" in address else address
        default_port = 443 if self.scheme == "https" else 80
        authority = literal if self.port == default_port else f"{literal}:{self.port}"
        return urlunsplit((self.scheme, authority, parsed.path or "/", parsed.query, ""))

    @property
    def host_header(self) -> str:
        """Return the original validated authority for HTTP Host routing."""

        default_port = 443 if self.scheme == "https" else 80
        return self.host if self.port == default_port else f"{self.host}:{self.port}"

    @property
    def request_extensions(self) -> dict[str, str]:
        """Preserve certificate validation for the original host over a pinned IP."""

        return {"sni_hostname": self.host}


Resolver = Callable[[str, int], Iterable[str]]

_RFC1918 = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)
_IPV6_ULA = ipaddress.ip_network("fc00::/7")
_METADATA_ADDRESSES = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("fd00:ec2::254"),
}
def _default_resolver(host: str, port: int) -> Iterable[str]:
    for _, _, _, _, sockaddr in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM):
        yield sockaddr[0]


def _normalize_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise SSRFValidationError(
            f"Resolved address {value!r} is invalid",
            reason="invalid_resolved_address",
        ) from exc
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        return address.ipv4_mapped
    return address


def _is_suspicious_numeric_host(host: str) -> bool:
    """Detect legacy integer/hex/octal IPv4 spellings without a regular expression."""

    labels = host.casefold().split(".")
    if not labels or any(not label for label in labels):
        return False
    return all(
        label.isdecimal()
        or (
            label.startswith("0x")
            and len(label) > 2
            and all(character in "0123456789abcdef" for character in label[2:])
        )
        for label in labels
    )


def _is_private_network(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(address, ipaddress.IPv4Address):
        return any(address in network for network in _RFC1918)
    return address in _IPV6_ULA


def _is_always_blocked(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        address in _METADATA_ADDRESSES
        or address.is_link_local
        or address.is_multicast
        or address.is_unspecified
        or (address.is_reserved and not address.is_loopback)
    )


Network = ipaddress.IPv4Network | ipaddress.IPv6Network


def _parse_allowlist(entries: str | Iterable[str]) -> tuple[set[str], tuple[Network, ...]]:
    raw_entries = entries.split(",") if isinstance(entries, str) else list(entries)
    hosts: set[str] = set()
    networks: list[Network] = []
    for raw in raw_entries:
        item = str(raw).strip().casefold().rstrip(".")
        if not item:
            continue
        try:
            networks.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            hosts.add(item)
    return hosts, tuple(networks)


def _hostname_is_allowlisted(host: str, allowed_hosts: set[str]) -> bool:
    normalized = host.casefold().rstrip(".")
    for entry in allowed_hosts:
        if entry.startswith("*."):
            suffix = entry[1:]
            if normalized.endswith(suffix) and normalized != suffix[1:]:
                return True
        elif normalized == entry:
            return True
    return False


def _address_is_allowlisted(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
    networks: tuple[Network, ...],
) -> bool:
    return any(address.version == network.version and address in network for network in networks)


def _reject(message: str, *, reason: str, host: str | None = None) -> SSRFValidationError:
    return SSRFValidationError(message, reason=reason, host=host)


def validate_outbound_url(
    url: str,
    *,
    policy: OutboundDestinationPolicy | str,
    allowlist: str | Iterable[str] = (),
    allow_http_on_private_network: bool = True,
    allow_http_on_public_network: bool = False,
    allowed_ports: Iterable[int] | None = None,
    resolver: Resolver = _default_resolver,
) -> ValidatedDestination:
    """Validate and resolve an outbound URL immediately before a request."""

    try:
        selected_policy = OutboundDestinationPolicy(policy)
    except ValueError as exc:
        raise _reject(f"Unknown outbound destination policy: {policy!r}", reason="invalid_policy") from exc

    parsed = urlsplit(url)
    scheme = parsed.scheme.casefold()
    if scheme not in {"http", "https"}:
        raise _reject(f"Unsupported URL scheme: {parsed.scheme!r}", reason="unsupported_scheme")
    if parsed.username is not None or parsed.password is not None:
        raise _reject("Credentials in outbound URLs are not allowed", reason="embedded_credentials")
    if not parsed.hostname:
        raise _reject("URL has no hostname", reason="missing_hostname")

    host = parsed.hostname.casefold().rstrip(".")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if _is_suspicious_numeric_host(host):
            raise _reject(
                f"Ambiguous numeric hostname {host!r} is not allowed",
                reason="ambiguous_numeric_host",
                host=host,
            )

    try:
        port = parsed.port or (443 if scheme == "https" else 80)
    except ValueError as exc:
        raise _reject("URL contains an invalid port", reason="invalid_port", host=host) from exc
    if allowed_ports is not None and port not in {int(value) for value in allowed_ports}:
        raise _reject(
            f"Port {port} is not allowed for this endpoint",
            reason="blocked_port",
            host=host,
        )

    try:
        resolved = tuple(dict.fromkeys(_normalize_ip(value) for value in resolver(host, port)))
    except socket.gaierror as exc:
        raise _reject(
            f"Could not resolve host {host!r}",
            reason="dns_failure",
            host=host,
        ) from exc
    if not resolved:
        raise _reject(f"Host {host!r} resolved to no addresses", reason="dns_empty", host=host)

    allowed_hosts, allowed_networks = _parse_allowlist(allowlist)
    hostname_allowlisted = _hostname_is_allowlisted(host, allowed_hosts)

    for address in resolved:
        if _is_always_blocked(address):
            raise _reject(
                f"URL host {host!r} resolves to blocked address {address}",
                reason="always_blocked_address",
                host=host,
            )

        if selected_policy is OutboundDestinationPolicy.PUBLIC_ONLY and not address.is_global:
            raise _reject(
                f"URL host {host!r} does not resolve exclusively to public addresses",
                reason="non_public_address",
                host=host,
            )
        if selected_policy is OutboundDestinationPolicy.PRIVATE_ALLOWED and address.is_loopback:
            raise _reject(
                f"Loopback address {address} requires loopback_allowed or an allowlist",
                reason="loopback_not_allowed",
                host=host,
            )
        if selected_policy is OutboundDestinationPolicy.PRIVATE_ALLOWED and not (
            address.is_global or _is_private_network(address)
        ):
            raise _reject(
                f"Address {address} is outside approved public and private ranges",
                reason="unsupported_private_range",
                host=host,
            )
        if selected_policy is OutboundDestinationPolicy.LOOPBACK_ALLOWED and not (
            address.is_global or _is_private_network(address) or address.is_loopback
        ):
            raise _reject(
                f"Address {address} is outside approved public, private, and loopback ranges",
                reason="unsupported_loopback_range",
                host=host,
            )
        if selected_policy is OutboundDestinationPolicy.LOOPBACK_ONLY and not address.is_loopback:
            raise _reject(
                f"Address {address} is not a loopback destination",
                reason="non_loopback_address",
                host=host,
            )
        if selected_policy is OutboundDestinationPolicy.ALLOWLIST_ONLY and not (
            hostname_allowlisted or _address_is_allowlisted(address, allowed_networks)
        ):
            raise _reject(
                f"URL host {host!r} is not in the outbound allowlist",
                reason="allowlist_miss",
                host=host,
            )

    if scheme == "http":
        contains_public = any(address.is_global for address in resolved)
        contains_private = any(_is_private_network(address) or address.is_loopback for address in resolved)
        if contains_public and not allow_http_on_public_network:
            raise _reject(
                "Unencrypted HTTP is disabled for public destinations",
                reason="public_http_disabled",
                host=host,
            )
        if contains_private and not allow_http_on_private_network:
            raise _reject(
                "Unencrypted HTTP is disabled for private destinations",
                reason="private_http_disabled",
                host=host,
            )

    return ValidatedDestination(
        url=url,
        scheme=scheme,
        host=host,
        port=port,
        addresses=resolved,
    )


def log_blocked_outbound_request(
    exc: SSRFValidationError,
    *,
    endpoint_type: str,
    destination_policy: OutboundDestinationPolicy | str,
    actor: str = "primary_admin",
    workspace: str | None = None,
    posture: str | None = None,
    correlation_id: str | None = None,
    source_integration: str | None = None,
) -> None:
    """Emit a structured security event without URL credentials or query data."""

    event = {
        "event": "outbound_request_blocked",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "workspace": workspace,
        "endpoint_type": endpoint_type,
        "destination_host": exc.host,
        "destination_policy": (
            destination_policy.value
            if isinstance(destination_policy, OutboundDestinationPolicy)
            else str(destination_policy)
        ),
        "reason": exc.reason,
        "posture": posture,
        "source_integration": source_integration or endpoint_type,
        "correlation_id": correlation_id,
    }
    logger.warning("security_event=%s", json.dumps(event, sort_keys=True, separators=(",", ":")))
