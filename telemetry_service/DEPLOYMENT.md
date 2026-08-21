# Production deployment gates

Do not expose the telemetry service until every item is independently verified:

- Danish/EU privacy review and privacy notice version 1.0 published;
- EU region selected for compute, PostgreSQL, backups, logs, monitoring, and DNS;
- processor inventory, DPAs, ROPA, incident response, deletion, and backup expiry documented;
- TLS 1.2 minimum, HSTS, no redirects, JSON-only body limits, WAF and edge rate limits;
- reverse-proxy logs omit or irreversibly redact source IP addresses;
- HMAC and identity-proxy secrets are stored in a managed secret store;
- SSO named accounts, required Alpha Horizon group, MFA, and least privilege tested;
- database backups, restore, purge, deletion handling, and backup expiry tested;
- security scans, fuzzing, replay, injection, flood, token, and privilege tests pass;
- disabled-client packet capture shows zero connections to the telemetry domain.

The Compose template has no public port and an internal database network.
Production ingress and identity-proxy configuration are infrastructure-specific.
