# Shogun 1.47.0

## Security

- Gensui now binds to loopback by default and disables OpenAPI, Swagger UI, and ReDoc outside development mode.
- Gensui browser authentication now uses short-lived HttpOnly access cookies, rotating refresh cookies, and CSRF validation. JWT signing material is stored in a dedicated secret file rather than `.env` on new installations.
- A2A workspace mutations require infrastructure-administrator authorization, replay tracking is capped at 10,000 entries, and peer secrets use a dedicated encryption key.
- Server-mode A2A publishing requires an explicit HTTPS public URL.
- Audit events now capture the direct client address and honor forwarded addresses only from configured trusted proxies.

## Reliability

- Tenshu now surfaces sanitized database migration and repair warnings so operators can act on degraded startup state.

## Security contributors

Thank you to @wstlima for the valuable security and deployment review that informed this hardening release.
