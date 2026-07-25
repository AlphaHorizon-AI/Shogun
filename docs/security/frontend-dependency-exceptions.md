# Frontend dependency security exceptions

## GHSA-qwww-vcr4-c8h2 — React Router RSC Mode CSRF bypass

- **Status:** Temporary approved exception
- **Reviewed:** 2026-07-25
- **Expires:** 2026-08-31
- **Affected lockfiles:** `frontend/package-lock.json`, `gensui/frontend/package-lock.json`
- **Review owner:** Alpha Horizon

At review time, npm's advisory ranges leave no React Router 7.x version that
clears every High advisory: versions through 7.17.0 are covered by earlier
router advisories, while GHSA-qwww-vcr4-c8h2 begins at 7.12.0 and has no
compatible patched 7.x release. Downgrading would reintroduce the older XSS,
open-redirect, denial-of-service, and deserialization findings.

Shogun and Gensui use React Router as browser-only single-page applications.
They do not enable React Server Components, SSR, Framework Mode server actions,
route actions, or RSC action endpoints. The vulnerable RSC request path is
therefore not reachable in either shipped frontend.

The CI audit gate permits only the exact advisory URL
`https://github.com/advisories/GHSA-qwww-vcr4-c8h2`. Any other High or Critical
finding fails the build. Remove this exception as soon as a compatible patched
React Router release is available. Otherwise reassess migration from
`react-router-dom` 7 to React Router 8 before the expiration date, then
regenerate both lockfiles.
