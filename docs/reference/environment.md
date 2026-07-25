# Security and deployment environment variables

| Variable | Default | Purpose |
|---|---|---|
| `SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN` | empty on desktop; required in server mode | Authorizes A2A peer invitations and Gensui connect/test/disconnect operations |
| `A2A_DESTINATION_POLICY` | `private_allowed` | A2A outbound policy |
| `GENSUI_DESTINATION_POLICY` | `loopback_allowed` on desktop; `private_allowed` in server Compose | Gensui outbound policy |
| `OUTBOUND_ALLOWLIST` | empty | Comma-separated exact hosts, `*.domain` wildcards, IPs, and CIDRs |
| `ALLOW_HTTP_ON_PRIVATE_NETWORK` | `true` | Permit HTTP for private/loopback destinations |
| `ALLOW_HTTP_ON_PUBLIC_NETWORK` | `false` | Permit unencrypted HTTP for public destinations |
| `A2A_ALLOWED_PORTS` | empty | Optional comma-separated A2A port allowlist |
| `GENSUI_ALLOWED_PORTS` | empty | Optional comma-separated Gensui port allowlist |
| `GENSUI_FRONTEND_DIST` | `gensui/frontend/dist` | Canonical Gensui frontend distribution directory |
| `GENSUI_DATA_PATH` | `gensui/data` | Gensui writable data directory |
| `GENSUI_LOG_PATH` | `gensui/logs` | Gensui writable log directory |

See [Outbound destination security](../security/outbound-destination-policy.md)
for policy semantics and [Docker deployment](../deployment/docker.md) for
container values and migration steps.
