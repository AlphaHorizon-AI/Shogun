"""Network Scanner — LAN discovery of Shogun instances.

Scans the local network for hosts running Shogun (port 8000) and
cross-references them against enrolled members to detect rogue agents.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import time
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from gensui.db.models.shogun_member import ShogunMember

log = logging.getLogger("gensui.network_scanner")

# Default Shogun port
SHOGUN_PORT = 8000

# Timeouts (seconds)
TCP_CONNECT_TIMEOUT = 0.5
HTTP_IDENTIFY_TIMEOUT = 2.0

# Max concurrent probes
MAX_CONCURRENT = 60


def _get_local_ips() -> set[str]:
    """Get all IPv4 addresses belonging to this machine."""
    local_ips: set[str] = set()
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            local_ips.add(info[4][0])
    except Exception:
        pass
    # Fallback: outbound socket trick
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        s.connect(("8.8.8.8", 80))
        local_ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    local_ips.add("127.0.0.1")
    return local_ips


def _get_local_subnets() -> list[str]:
    """Discover /24 subnets from the machine's own network interfaces.

    Returns a list of subnet prefixes like ["192.168.1.", "10.0.0."].
    """
    subnets: set[str] = set()
    for ip in _get_local_ips():
        if ip.startswith("127."):
            continue
        parts = ip.split(".")
        if len(parts) == 4:
            prefix = ".".join(parts[:3]) + "."
            subnets.add(prefix)
    return list(subnets)


def _build_probe_ips(subnets: list[str]) -> list[str]:
    """Build a deduplicated probe list that always includes this machine.

    Desktop Shogun binds to loopback by default, so LAN-only probing can never
    discover a Shogun running beside Gensui on the same computer.
    """
    ips = ["127.0.0.1"]
    for subnet in subnets:
        ips.extend(f"{subnet}{i}" for i in range(1, 255))
    return list(dict.fromkeys(ips))


async def _probe_tcp(ip: str, port: int, timeout: float = TCP_CONNECT_TIMEOUT) -> bool:
    """Check if a TCP port is open on a given IP. Returns True if connectable."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=timeout,
        )
        writer.close()
        await writer.wait_closed()
        return True
    except (asyncio.TimeoutError, OSError, ConnectionRefusedError):
        return False


async def _identify_shogun(ip: str, port: int) -> dict[str, Any] | None:
    """Try to identify a Shogun instance by hitting its health endpoint.

    Returns instance info dict or None if not a Shogun.
    """
    url = f"http://{ip}:{port}/api/v1/health"
    try:
        async with httpx.AsyncClient(timeout=HTTP_IDENTIFY_TIMEOUT) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("service") == "shogun":
                    return {
                        "version": data.get("version"),
                        "instance_name": data.get("instance_name"),
                        "shogun_id": data.get("shogun_id"),
                    }
    except Exception:
        pass

    # Fallback: try the root API endpoint
    try:
        url_root = f"http://{ip}:{port}/api/v1/version"
        async with httpx.AsyncClient(timeout=HTTP_IDENTIFY_TIMEOUT) as client:
            resp = await client.get(url_root)
            if resp.status_code == 200:
                data = resp.json()
                if "version" in data:
                    return {
                        "version": data.get("version"),
                        "instance_name": data.get("name", "Unknown"),
                        "shogun_id": data.get("shogun_id"),
                    }
    except Exception:
        pass

    return None


async def _scan_host(
    ip: str,
    port: int,
    semaphore: asyncio.Semaphore,
    local_ips: set[str],
) -> dict[str, Any] | None:
    """Scan a single host: TCP probe → HTTP identify."""
    async with semaphore:
        if not await _probe_tcp(ip, port):
            return None

        # Port is open — try to identify
        info = await _identify_shogun(ip, port)

        # Resolve hostname
        hostname = None
        try:
            hostname = socket.getfqdn(ip)
            if hostname == ip:
                hostname = None
        except Exception:
            pass

        return {
            "ip": ip,
            "port": port,
            "hostname": hostname,
            "is_shogun": info is not None,
            "is_self": ip in local_ips,
            "version": info.get("version") if info else None,
            "instance_name": info.get("instance_name") if info else None,
            "shogun_id": info.get("shogun_id") if info else None,
        }


def _deduplicate_hosts(hosts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate Shogun instances found on multiple network interfaces.

    Groups by shogun_id, instance_name, or 'self' flag and merges IPs.
    Non-Shogun hosts are passed through unchanged.
    """
    non_shogun = [h for h in hosts if not h.get("is_shogun")]
    shogun_hosts = [h for h in hosts if h.get("is_shogun")]

    # Group by identity key — prioritize shogun_id, then instance_name,
    # then use "__self__" for all local-machine hits (same machine, different NICs)
    groups: dict[str, list[dict[str, Any]]] = {}
    for h in shogun_hosts:
        key = h.get("shogun_id") or h.get("instance_name")
        if not key:
            # No identity — fall back to self-detection grouping
            key = "__self__" if h.get("is_self") else h["ip"]
        groups.setdefault(key, []).append(h)

    deduped: list[dict[str, Any]] = []
    for key, group in groups.items():
        primary = group[0]
        all_ips = sorted({h["ip"] for h in group})
        is_self = any(h.get("is_self") for h in group)

        merged = {**primary}
        merged["ip"] = ", ".join(all_ips) if len(all_ips) > 1 else all_ips[0]
        merged["all_ips"] = all_ips
        merged["interface_count"] = len(all_ips)
        merged["is_self"] = is_self
        deduped.append(merged)

    return deduped + non_shogun


async def scan_network(
    session: AsyncSession,
    subnets: list[str] | None = None,
    port: int = SHOGUN_PORT,
) -> dict[str, Any]:
    """Scan the local network for Shogun instances.

    Args:
        session: Database session for cross-referencing enrolled members.
        subnets: Optional list of /24 subnet prefixes. Auto-detected if None.
        port: Port to scan (default 8000).

    Returns a dict with discovered hosts, scan metadata, and classification.
    """
    start = time.monotonic()

    # Collect local IPs for self-detection
    local_ips = _get_local_ips()

    # Discover subnets
    if subnets is None:
        subnets = _get_local_subnets()

    log.info("[NetworkScanner] Scanning subnets: %s (port %d)", subnets, port)

    # Build IP list
    ips = _build_probe_ips(subnets)

    # Scan all IPs concurrently (with semaphore)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    tasks = [_scan_host(ip, port, semaphore, local_ips) for ip in ips]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Collect discovered hosts (filter None and exceptions)
    raw_discovered: list[dict[str, Any]] = []
    for r in results:
        if isinstance(r, dict):
            raw_discovered.append(r)

    # Deduplicate same-instance hits across multiple interfaces
    discovered = _deduplicate_hosts(raw_discovered)

    # Load all enrolled members for cross-reference
    result = await session.execute(
        select(ShogunMember).where(ShogunMember.enrollment_status.in_(["active", "pending"]))
    )
    members = list(result.scalars().all())

    # Build lookup sets
    enrolled_hostnames = {m.hostname for m in members if m.hostname}
    enrolled_ids = {str(m.id) for m in members}
    enrolled_names = {m.instance_name for m in members if m.instance_name}

    # Classify discovered hosts
    enrolled_hosts = []
    unenrolled_hosts = []
    unknown_hosts = []

    for host in discovered:
        if not host["is_shogun"]:
            host["classification"] = "unknown"
            unknown_hosts.append(host)
            continue

        # Check if this Shogun is enrolled
        is_enrolled = False

        # Match by shogun_id
        if host.get("shogun_id") and host["shogun_id"] in enrolled_ids:
            is_enrolled = True
            host["matched_by"] = "shogun_id"

        # Match by hostname
        elif host.get("hostname") and host["hostname"] in enrolled_hostnames:
            is_enrolled = True
            host["matched_by"] = "hostname"

        # Match by instance_name
        elif host.get("instance_name") and host["instance_name"] in enrolled_names:
            is_enrolled = True
            host["matched_by"] = "instance_name"

        # Match by IP as hostname
        elif host["ip"] in enrolled_hostnames:
            is_enrolled = True
            host["matched_by"] = "ip"

        if is_enrolled:
            host["classification"] = "enrolled"
            enrolled_hosts.append(host)
        else:
            host["classification"] = "unenrolled"
            unenrolled_hosts.append(host)

    duration_ms = int((time.monotonic() - start) * 1000)
    log.info(
        "[NetworkScanner] Scan complete: %d unique hosts (%d raw hits, %d enrolled, %d unenrolled, %d unknown) in %dms",
        len(discovered), len(raw_discovered), len(enrolled_hosts), len(unenrolled_hosts), len(unknown_hosts), duration_ms,
    )

    return {
        "hosts": discovered,
        "enrolled": enrolled_hosts,
        "unenrolled": unenrolled_hosts,
        "unknown": unknown_hosts,
        "subnets_scanned": subnets,
        "total_ips_probed": len(ips),
        "raw_hits": len(raw_discovered),
        "scan_duration_ms": duration_ms,
        "timestamp": time.time(),
    }
