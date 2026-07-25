# Enterprise telemetry controls

Enterprises may keep `SHOGUN_TELEMETRY=off` or block
`telemetry.alphahorizon.io` in DNS/firewall policy. No Shogun capability depends
on the endpoint.

Team Mode changes require the infrastructure/Primary Admin credential. Ordinary
members cannot call telemetry routes. Status is installation-level and never
includes member identity or member count.

The Alpha Horizon console must sit behind an EU-hosted SSO identity proxy that
injects authenticated email, group membership, and MFA assertions plus the
independent proxy secret. Do not expose the service directly without TLS, HSTS,
body limits, WAF/rate limiting, redacted access logs, monitoring, backups, and
tested deletion and restore procedures.
