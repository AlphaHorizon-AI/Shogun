# Unreleased — Security and deployment hardening

This release accepts and remediates the public findings in issues #3–#11.

## Security

- Escapes user-controlled Kaizen mandate content before the supported Markdown
  subset is converted to HTML, preventing stored script/HTML execution.
- Adds policy-based outbound destination controls for A2A and Gensui with
  permanent metadata/link-local blocking, all-address DNS checks, disabled
  redirects, scheme and port controls, allowlists, and structured security logs.
- Restricts infrastructure-changing routes to the local Primary Admin in
  desktop mode or a secret infrastructure token in server mode.
- Refreshes both frontend dependency trees. One non-reachable React Router RSC
  advisory has a narrow, machine-enforced temporary exception documented in
  `docs/security/frontend-dependency-exceptions.md`.

## Gensui Docker

- Declares the bcrypt and PyJWT runtime dependencies.
- Uses a canonical configurable frontend distribution path and always builds the
  Gensui UI from the repository-root Docker context.
- Adds the official local-only Compose profile, generated secrets, health
  ordering, a non-root runtime, read-only application filesystem, dropped
  capabilities, and `no-new-privileges`.
- Existing root-owned volumes must be backed up and changed to UID/GID 1000.
  Full migration and rollback commands are in `docs/deployment/docker.md`.

## Shogun Server / Headless

- Documents the production container as a Server / Headless profile rather than
  native-feature parity.
- Validates non-root Playwright installation, health, persistent state, local
  binding, and explicit Ronin/Office limitations in CI.

## Prevention

- Adds Python, frontend, dependency, CodeQL, Docker smoke, secret,
  misconfiguration, and image scan gates.
- Pins Node 22 as the supported build major and adds weekly dependency and
  container checks.

## Security contributors

Special thanks to [@wstlima](https://github.com/wstlima) for the valuable,
well-documented security, dependency, Docker, and deployment review behind
issues #3–#11 and pull requests #12–#20. Alpha Horizon reviewed and accepted the
findings; the original straightforward pull requests were merged so the
contribution remains visibly attached to Shogun's history. PRs #18 and #20 were
accepted through architecture-adjusted replacement implementations.
