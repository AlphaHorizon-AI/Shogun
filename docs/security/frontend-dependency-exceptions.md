# Frontend dependency security exceptions

## GHSA-qwww-vcr4-c8h2 — React Router RSC Mode CSRF bypass

- **Status:** Removed on 2026-09-09; no active exception
- **Reviewed:** 2026-07-25
- **Expires:** 2026-08-31
- **Affected lockfile:** `frontend/package-lock.json`
- **Review owner:** Alpha Horizon

At review time, npm's advisory ranges leave no React Router 7.x version that
clears every High advisory: versions through 7.17.0 are covered by earlier
router advisories, while GHSA-qwww-vcr4-c8h2 begins at 7.12.0 and has no
compatible patched 7.x release. Downgrading would reintroduce the older XSS,
open-redirect, denial-of-service, and deserialization findings.

The Tenshu uses React Router as a browser-only single-page application.
It does not enable React Server Components, SSR, Framework Mode server actions,
route actions, or RSC action endpoints. The vulnerable RSC request path is
therefore not reachable in the shipped frontend.

The current locked router no longer reports this advisory. The expired exception
has been removed: every High or Critical finding fails the build. Audit API,
process, or report-format failures also fail the gate. Lower-severity findings
are reported explicitly and are never described as approved exceptions.

The history above records the original exception rationale; it grants no current
exception. Vitest and humanfs findings discovered on 2026-09-09 were patched in
the lockfile rather than exempted.
