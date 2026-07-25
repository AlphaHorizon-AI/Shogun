# Shogun 1.46.0

This release strengthens Shogun's security boundaries across desktop and server deployments.

- Added control-plane authentication, rate limiting, and browser security headers.
- Hardened A2A, Nexus, and Gensui authentication and task ownership checks.
- Restricted outbound destinations and protected stored and returned credentials.
- Added fail-closed production configuration checks and safer installer defaults.
- Added regression coverage for the new security controls.

Existing desktop installations remain local-first. Server operators must configure strong application, vault, and infrastructure-administrator secrets before startup.

## Security contributors

Thank you to [@wstlima](https://github.com/wstlima) for the valuable, well-documented security and deployment review that informed this hardening work.
