# Shogun 1.47.6

CI and hardened-container compatibility release.

## Reliability and security

- Prevented the server profile from attempting to rewrite `.env` inside its read-only application filesystem.
- Passed Gensui's database, data, log, and JWT secret paths explicitly to writable mounted volumes in its hardened smoke test.
- Made the security workflow's Ruff rule selection explicit and retained FastAPI dependency injection compatibility.
- Corrected import ordering in the Gensui authentication and identity boundary modules.
