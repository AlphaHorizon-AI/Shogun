# Yellow Label activation verification — 23 October 2026

The Windows desktop installation was started through its existing launcher and restarted through the authenticated updater endpoint. The replacement process reports **running and installed version 1.47.119, build 270**, with `restart_required=false`. Verification used loopback port 8001 because another application owns port 8000; the original `.env` and credentials were retained.

Live testing found and corrected three compatibility issues:

- The desktop launchers forced the browser to port 8000. They now leave endpoint resolution to the Python entry point, honoring configuration and explicit browser URL overrides. Existing-listener detection also requires Shogun's healthy service identity.
- The persisted SkillOpt Regression Sweep preset failed schedule-response validation. Its existing job type is now included in the enum, and every shipped preset is covered by the schedule-list regression test.
- Local Ollama discovery deleted saved provider configuration when a different or temporarily incomplete inventory was returned. Discovery is now additive. Three affected provider rows and their three catalog rows were restored from the consistent pre-start SQLite backup without overwriting other records. Empty and changed inventory regressions verify preservation of provider identities and custom configuration.

## Executed verification

| Check | Result |
| --- | --- |
| Complete backend security gate, lint, clean import, translation consistency and telemetry contract | 688 passed, 4 platform skips; all other checks passed |
| Frontend TypeScript/Vite build and bundle limit | Passed; 101 chunks, largest 385.10 KiB |
| Fresh headless browser navigation | 16 Yellow Label pages rendered; no JavaScript exceptions or API server errors |
| Authenticated feature API smoke | 27 endpoints returned HTTP 200 |
| Updater version and remote check | Running/installed 1.47.119 / 270; remote check successful |
| Privileged endpoint authentication | Anonymous read/apply/restart requests rejected with HTTP 401 |
| Apply with local changes | HTTP 409 before download/promotion, preserving the working tree |
| Authenticated updater restart | HTTP 202; launcher replaced the server process and retained the configured port |
| Yellow Label enterprise boundary | Restricted Gensui endpoints returned HTTP 403 |
| Persistence comparison | Original tables, record identifiers, files, credentials, operator settings and schedule definitions preserved; SQLite integrity and schema checks passed |
| Existing Qdrant storage | Original mount and collection healthy; stored point total retained |

Normal runtime state changed: audit events were appended, next-run timestamps advanced, inferred model capability metadata refreshed, and telemetry delivery bookkeeping updated under existing consent. No new consent, credential reset, bulk database restore, volume recreation or saved browser profile use was part of the verification.

Private backups, fingerprints and smoke results remain in the installation's ignored `tmp/emudhra-maintenance/activation/` directory. They are not release assets. External account actions, model downloads, destructive workflows and live code promotion over the dirty checkout were not exercised; preparation/promotion and failure recovery remain covered by the updater regressions.
