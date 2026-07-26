# Docker deployment and migration

Both official profiles bind only to localhost unless an operator explicitly
changes the binding.

## Shogun Server / Headless profile

```bash
cp .env.server.example .env.server
# Replace every change-me value.
docker compose --env-file .env.server -f docker-compose.server.yml up -d --build
```

The profile runs as UID/GID 10001 with a read-only root filesystem, all Linux
capabilities dropped, `no-new-privileges`, dedicated PostgreSQL and Qdrant
services, and persistent application, vault, log, and configuration volumes.
Playwright browsers are installed at `/ms-playwright` and are executable by the
runtime user.

| Capability | Native Windows | Native Linux | Native macOS | Server / Headless Docker |
|---|---:|---:|---:|---:|
| Core runtime and Tenshu UI | Yes | Yes | Yes | Yes |
| Team Mode, Agent Flows, stacks | Yes | Yes | Yes | Yes |
| Gensui, Nexus, Telegram, Teams | Yes | Yes | Yes | Yes |
| Mado headless Chromium | Yes | Yes | Yes | Yes |
| Mado visible browser | Yes | Environment-dependent | Environment-dependent | No by default |
| Office App Mode / Windows COM | Yes | No | No | No |
| Ronin host-desktop control | Yes | Environment-dependent | Environment-dependent | No |
| Host or LAN model server | Yes | Yes | Yes | Yes, with explicit network configuration |

Do not describe this profile as native-feature parity. Use native Windows when
Office COM or full Ronin desktop control is required.

## Gensui

The Gensui Dockerfile must be built from the repository root:

```bash
docker build -f gensui/Dockerfile .
cd gensui
cp .env.example .env
# Replace the administrator password placeholder.
docker compose up -d --build
```

The default publishes `127.0.0.1:8787`, runs as UID/GID 1000, drops every
capability, enables `no-new-privileges`, uses a read-only root filesystem, and
writes only to `/app/data`, `/app/logs`, and `/tmp`. The optional `server`
profile starts Nginx for operator-supplied TLS certificates.

The one-click installers generate the initial administrator password in the
protected `.env` file. JWT signing material is generated separately in the
persistent `data/secrets` volume and is never written to `.env`. Rotate the
administrator password after first login.

## Existing Gensui volume migration

Back up before changing ownership:

```bash
docker compose down
docker run --rm -v gensui_data:/data -v "$PWD:/backup" alpine \
  tar czf /backup/gensui-data-backup.tgz -C /data .
docker run --rm -v gensui_logs:/logs -v "$PWD:/backup" alpine \
  tar czf /backup/gensui-logs-backup.tgz -C /logs .
```

Repair volumes created by the former root container:

```bash
docker run --rm -v gensui_data:/data alpine chown -R 1000:1000 /data
docker run --rm -v gensui_logs:/logs alpine chown -R 1000:1000 /logs
docker compose up -d
```

Verify `docker exec gensui whoami`, the health endpoint, login, database writes,
and logs. To roll back, stop the new container, restore the backup archives into
the named volumes, and start the previously pinned image. Do not delete volumes
until the migrated deployment has been verified.
