# Docker deployment

The official Server profile binds only to localhost unless an operator explicitly changes the binding.

## Shogun Server / Headless profile

```bash
cp .env.server.example .env.server
# Replace every change-me value.
docker compose --env-file .env.server -f docker-compose.server.yml up -d --build

# Print the private infrastructure-administrator bootstrap link.
docker compose --env-file .env.server -f docker-compose.server.yml exec -T shogun \
  python -m shogun.setup_link --origin http://127.0.0.1:8000
```

Use the installer-generated or explicitly printed link for first setup. Its infrastructure credential is URL-encoded after `#`, so it is not sent in an HTTP request or referrer header. The frontend removes the fragment before its first API request and retains the credential only in that browser tab's `sessionStorage`.

Treat the complete link as a long-lived administrator credential. Do not put it in a query string, bookmark, screenshot, chat, issue, or shared log. Rotate `SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN` if it is disclosed.

The profile runs as UID/GID 10001 with a read-only root filesystem, all Linux capabilities dropped, `no-new-privileges`, dedicated PostgreSQL and Qdrant services, and persistent application, vault, log, and configuration volumes. Playwright browsers are installed at `/ms-playwright` and are executable by the runtime user.

| Capability | Native Windows | Native Linux | Native macOS | Server / Headless Docker |
|---|---:|---:|---:|---:|
| Core runtime and Tenshu UI | Yes | Yes | Yes | Yes |
| AgentFlows and Telegram | Yes | Yes | Yes | Yes |
| Mado headless Chromium | Yes | Yes | Yes | Yes |
| Mado visible browser | Yes | Environment-dependent | Environment-dependent | No by default |
| Office App Mode / Windows COM | Yes | No | No | No |
| Ronin host-desktop control | Yes | Environment-dependent | Environment-dependent | No |
| Host or LAN model server | Yes | Yes | Yes | Yes, with explicit network configuration |

Use native Windows when Office COM or full Ronin desktop control is required.
