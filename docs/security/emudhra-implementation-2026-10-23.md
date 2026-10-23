# Yellow Label eMudhra implementation — 23 October 2026

The security maintenance release is **1.47.119, build 270**. Python trust, Node selection, installers and both updater paths are corrected. Windows and WSL each passed all 45 live incident checks. Ubuntu WSL recovered after the approved restart following host disk exhaustion; its corrected trust, native regressions and existing Qdrant data were verified again.

The release is based on remote main `ede4b879f8acff9aeff97ff141c353c888adb06f`, which already contains the workbook releases through 1.47.118. An isolated checkout keeps unrelated local integration changes out of the security commit. The build paper is version 1.4 in the repository and its original Downloads location. No existing application database, credentials, approval state, saved browser profile or persistent container volume was replaced or removed.

**Implemented changes**

- certifi >=2026.10.19 and pip >=26.2.2, bootstrapped from independently hash-authenticated exact wheels before ordinary package downloads.
- Corrected Node 22/24 floors in installers, package/lock metadata, launchers, updater, CI and containers. Application-owned Node 24.22.1 is selected explicitly for npm and Playwright; global runtimes and saved browser profiles are retained.
- Read-only checks for affected roots and the 12 known affected TLS intermediate/cross-sign certificate identities in Python/custom PEM trust. Effective Linux native trust is also checked.
- Immutable updater source resolution, administrator authorization, Yellow Label validation, protected-state exclusions and dependency/frontend preparation before application-file promotion.
- Safe preparation failures, recoverable code promotion, and worker-owned locks/temporary files that remain valid after HTTP cancellation.
- Shared in-app/repair preparation, public incident fixtures, credential-free live diagnostics and an operator runbook.
- Vitest 4.1.12 and matching lockfile corrections for the two additional advisories found by the required dependency gate. [Maintainer code-injection advisory](https://github.com/vitest-dev/vitest/security/advisories/GHSA-qxg6-89mg-rqv8), [maintainer Windows traversal advisory](https://github.com/vitest-dev/vitest/security/advisories/GHSA-xp26-3454-mjgp).
- Native CA correction before CI's Python dependency downloads; no TLS verification bypass.
- Immutable server/telemetry images exclude pip, its ensurepip seed and npm after build preparation, removing the vulnerable bundled tooling reported by image scans. Corrected Node, the built UI, Playwright/Chromium and application dependencies remain. Desktop installers and updaters retain pip/npm.
- Runtime-only trust validation is read-only and cannot bypass installer bootstrap. Official container updates require image replacement through the deployment platform with existing volumes; desktop update preparation still requires corrected package managers.

No schema migration or edition conversion was introduced. No PHP source or Composer application was identified in this repository; the separate PHP RCE advisories and corrected branches remain documented in the build paper.

**Verification of the isolated release source**

| Check | Result |
| --- | --- |
| Complete required backend security gate, including workbook, SkillOpt, ToolGate, Ronin, Mado, installer and updater regressions | 662 passed, 4 platform-specific skips |
| Backend lint, guide synchronization, clean application import and telemetry privacy contract | PASS |
| Native Linux shell, security policy and updater regressions | 83 passed, no skips |
| Windows dependency consistency (`pip check`) | PASS |
| Fresh venv authenticated bootstrap from seeded pip 25.2 | PASS: pip 26.2.2 and certifi 2026.10.19 |
| Existing Playwright/Chromium with corrected external Node | PASS: isolated headless page; saved profiles unopened |
| Locked frontend installation, TypeScript/Vite build, security lint and bundle check | PASS |
| Frontend security tests with patched Vitest 4.1.12 | 14 passed |
| Audit gate regression tests | 15 passed |
| Moderate/high/critical npm dependency findings after correction | None |
| Frontend bundle | 101 JavaScript chunks; largest 385.10 KiB, below 500 KiB |
| Windows live incident checks | 45 PASS, 0 FAIL, 0 INCONCLUSIVE |
| WSL live incident checks after native CA correction | 45 PASS, 0 FAIL, 0 INCONCLUSIVE |
| Container verification | Required CI builds both images, scans high/critical findings, tests non-root health and validates runtime trust; current results are on PR #85 |
| Native macOS | Both required native jobs passed on the initial security commit, including Safari after a runner retry; final source remains subject to those same PR gates |

Each live set covers the 14 published affected endpoints plus a legitimate positive control through HTTPX, pip's actual combined trust context and the selected Node runtime. The recorded WSL run completed before the later host disk failure. Offline fixtures additionally verify both Python CA bundles with fixed verifier times and an isolated original-root positive control; neither the machine clock nor host trust is changed by those tests.

The frontend was installed and built in the isolated release checkout. The active application's stale dependency cache was replaced with that tested, patched lockfile installation; its served assets and persistent state were retained. The release checkout shares the verified dependency cache to avoid duplicate storage. Temporary build copies were removed to recover host space; test evidence was retained.

**WSL repair and host recovery**

The authorized `dpkg --configure -a` completed the pre-existing pending package configuration. The targeted vendor CA update installed Ubuntu 24.04 `ca-certificates` **20260816ubuntu0.24.04.1**. The maintenance gate passed and pip's previous 14 accepted affected endpoints became 14 verified rejections. [Ubuntu correction](https://ubuntu.com/blog/emudhra-ca-compromise-fixes-available).

The WSL application environment has Python 3.12.3, pip 26.2.2, certifi 2026.10.19 and selected application-owned Node 24.22.1. Windows has the same corrected tooling with Python 3.14.0.

The first local Docker build filled the Windows host disk and WSL reported filesystem I/O errors. Disposable task-owned build copies were removed. Following explicit operator approval, Ubuntu WSL was restarted while retaining its filesystem and Docker volumes. The existing Qdrant container recovered with its mount intact; its retained collection is readable and its restart-error count is zero. The package database audit is clean, the maintenance gate passes, and a fresh live probe again recorded 45 PASS / 0 FAIL / 0 INCONCLUSIVE. No volume recreation, database restore or unrelated filesystem cleanup was used.

Independent CI then identified vulnerable components inside pip/npm's bundled build tooling. The final runtime packaging omits those build tools without modifying their vendored code or adding scan exceptions. The required container jobs exercise the resulting runtime, and the normal desktop installer/updater path retains its corrected tooling. [PR #85 and required checks](https://github.com/AlphaHorizon-AI/Shogun/pull/85) record the exact source revisions and executed platform, scan and runtime results.

**Evidence, artifacts and deployment**

Raw and sanitized local evidence is under `tmp/emudhra-maintenance/`; the release manifest identifies current verification and any superseded candidate artifacts. Earlier dirty-working-tree candidates are review evidence only and must not be published under an unrelated commit SHA. The final Git commit identifies the focused release source. The runbook is [emudhra-maintenance.md](emudhra-maintenance.md).

Live application migrations, remote updater execution, credential resets, database restores and user-profile tests were not performed. Restart an intended installation only through its established launcher/supervisor, then verify fresh process and TLS identities. Existing local Git edits intentionally block automatic updater application. Code recovery material is not an independently verified secure fallback; dependency installation is not transactional. Retain corrected trust when repairing forward.
