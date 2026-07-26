# Gensui deployment

For a native developer install, run `install.bat` on Windows or `./install.sh`
on macOS/Linux.

For the official Docker flow, use a repository-root build context:

```bash
cp gensui/.env.example gensui/.env
# Replace the administrator password placeholder. JWT signing material is
# generated in the persistent data/secrets volume on first start.
cd gensui
docker compose up -d --build
```

The default service is available only at `http://127.0.0.1:8787`. Remote access
must use an explicit VPN, authenticated gateway, enterprise ingress, or the
optional Nginx `server` profile with operator-managed TLS certificates. Do not
expose the service directly to the public internet.

Production mode disables OpenAPI, Swagger UI, and ReDoc. Set `DEBUG=true` only
for a local development instance. Browser sessions use short-lived HttpOnly
access cookies, rotating refresh cookies, and CSRF validation.

The container runs as UID/GID 1000 with a read-only root filesystem and writes
only to the data and log volumes. See
[`docs/deployment/docker.md`](../docs/deployment/docker.md) before upgrading an
existing root-owned deployment.
