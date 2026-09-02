# Enterprise telemetry controls

Enterprises may keep `SHOGUN_TELEMETRY=off` or block
`telemetry.alphahorizon.io` in DNS/firewall policy. No Shogun capability depends
on the endpoint.

Telemetry changes require the infrastructure-administrator credential in Server
mode. Status is installation-level and never includes operator identity.

The Alpha Horizon console must sit behind an EU-hosted SSO identity proxy that
injects authenticated email, group membership, and MFA assertions plus the
independent proxy secret. Do not expose the service directly without TLS, HSTS,
body limits, WAF/rate limiting, redacted access logs, monitoring, backups, and
tested deletion and restore procedures.
