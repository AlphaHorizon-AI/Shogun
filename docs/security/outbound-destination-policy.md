# Outbound destination security

Shogun applies one policy decision immediately before each user-configured A2A
or Gensui HTTP request. Every A and AAAA answer must pass. Automatic redirects
are disabled, URL credentials and ambiguous numeric hosts are rejected, and
cloud metadata, link-local, multicast, unspecified, and reserved addresses are
always blocked.

## Policies

| Policy | Intended use | Allowed destinations |
|---|---|---|
| `public_only` | Internet-only federation | Public addresses only |
| `private_allowed` | LAN, VPN, container DNS, on-premises Gensui/Nexus | Public, RFC 1918, and IPv6 ULA; no loopback |
| `loopback_allowed` | Explicit same-host desktop deployment | Public, private, and loopback |
| `allowlist_only` | Controlled enterprise deployment | Only configured hostnames, wildcard domains, IPs, and CIDRs |

Desktop Gensui defaults to `loopback_allowed` because the documented local
server is `http://localhost:8787`. The Shogun Server profile defaults both A2A
and Gensui to `private_allowed`. Use `allowlist_only` for the tightest enterprise
deployment.

## Configuration

```env
A2A_DESTINATION_POLICY=private_allowed
GENSUI_DESTINATION_POLICY=private_allowed
OUTBOUND_ALLOWLIST=gensui.internal,*.shogun.corp,10.40.0.0/16,fd42::/48
ALLOW_HTTP_ON_PRIVATE_NETWORK=true
ALLOW_HTTP_ON_PUBLIC_NETWORK=false
A2A_ALLOWED_PORTS=443,8000
GENSUI_ALLOWED_PORTS=443,8787
```

An empty port list allows any TCP port that otherwise passes policy. Restrict
ports when operators do not need custom service ports. Public HTTP is disabled
by default; private HTTP remains available for local and air-gapped deployments.

`allowlist_only` does not override the permanent metadata and link-local block.
If DNS returns a mixture of allowed and blocked addresses, the request fails.

## Infrastructure authorization

Server mode requires `SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN`. Paste that value into
the Infrastructure Admin Token field in the Gensui or Nexus screen. The browser
keeps it in `sessionStorage`, so it disappears when that tab session ends.
Desktop mode without a configured token accepts these privileged operations only
from a loopback client.

Blocked requests emit a structured `outbound_request_blocked` security log with
the actor, endpoint class, normalized hostname, policy, reason, and correlation
fields. Tokens, URL credentials, and query strings are not logged.

## DNS rebinding protection

Shogun resolves and validates every returned address immediately before opening
the request, then connects directly to one of those validated IP addresses. The
original hostname is retained in the HTTP `Host` header and TLS SNI extension,
so certificate and virtual-host validation continue to use the configured
hostname without a second DNS lookup. Redirect following and environment proxy
discovery are disabled for these guarded requests.

For high-assurance deployments, `allowlist_only`, controlled DNS, an egress
firewall, or a service mesh remain useful defense-in-depth controls.
