# Security and deployment environment variables

| Variable | Default | Purpose |
|---|---|---|
| `SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN` | generated in the protected desktop `.env`; required in server mode | Authorizes the operator control plane; launchers carry it in a URL fragment and the frontend retains it only for the tab session |
| `OUTBOUND_ALLOWLIST` | empty | Comma-separated exact hosts, `*.domain` wildcards, IPs, and CIDRs |
| `ALLOW_HTTP_ON_PRIVATE_NETWORK` | `true` | Permit HTTP for private/loopback destinations |
| `ALLOW_HTTP_ON_PUBLIC_NETWORK` | `false` | Permit unencrypted HTTP for public destinations |

See [Docker deployment](../deployment/docker.md) for container values and
migration steps.
