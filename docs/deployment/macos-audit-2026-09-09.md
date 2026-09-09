# macOS compatibility audit — 9 September 2026

Target: Apple Silicon M3–M5, macOS 14 or newer, native arm64 Python 3.12,
Node.js 22. Baseline revision: `09519a6ccdb554e923fb8a7219c16daf6260df70`.
The audit below was completed before publication; native macOS CI had not run
at that point. The fixes are included in the prepared 1.47.102 / build 253 update.

## Conclusion

Several installer and launcher defects were found and corrected. The complete
application dependency set resolves for Apple Silicon, including Office and
optional Ronin packages. **End-to-end operation on macOS is not yet certified:**
this audit ran on Windows, and the newly added native macOS CI workflow has not
been executed in this session. Ronin's Mac adapter also has explicit feature gaps.

## Corrected defects

| Area | Finding and correction |
| --- | --- |
| Prerequisites | Previously selected the first `python3` even when too old, and assumed a configured shell PATH. Search versioned interpreters, accept an explicit interpreter, and include normal Homebrew locations. Reject Intel/Rosetta Python, an existing Intel venv, and macOS older than 14 with an actionable message. |
| Dependency installation | Bind all Python/pip commands to the installation's venv, including when an absolute Python path was supplied. |
| Error handling | Chromium, database bootstrap, and frontend failures could be hidden behind success messages. Required failures now stop installation; frontend dependencies use the existing lockfile with `npm ci`. |
| Unattended installation | An unanswered Ronin prompt could terminate installation on EOF. Redirected input now declines it; add explicit Ronin options and `--no-start`. Forward downloader arguments to the installer. |
| Launcher | Use BSD-compatible symlink resolution, quote interpreter paths, stop on failed frontend repair, and retain the correct working directory. Include Homebrew locations for later frontend repair and updates. |
| First launch and restart | The installer now uses `start.sh` supervision and preserves the setup URL through the first launch. |
| Python re-execution | Comparing resolved interpreter paths incorrectly treated POSIX venv symlinks as the global environment. Detect the active venv via `sys.prefix` and preserve it when both `venv` and `.venv` exist. |
| Desktop shortcut | Generate a `.command` entry for Terminal, quote installation paths as shell literals, and propagate shortcut creation failures. |
| Uninstaller | Previously deleted the caller's current directory. Anchor removal to the script's installation, verify installation markers, refuse root/home/unrecognized locations, and report removal failures. Shell tests record removal targets without deleting an installation. |
| Documentation | Enforce LF for `.command` files, correct the prerequisite/double-click instructions, and document native requirements and missing capabilities. |

## Validation evidence

- Cross-target dependency resolution: **143 packages resolved** for
  `aarch64-apple-darwin`, Python 3.12, `office` and `ronin` extras. This checks
  dependency resolution, not execution of those packages on a Mac.
- Shell regression run: **25 passed, 1 skipped** using Git Bash on Windows.
  Covers download/upgrade flow, preserved setup and memory files, installer
  options, failure paths, architecture/OS/Node rejection, generated launcher
  quoting, safe uninstall targeting, and shell syntax/line endings. The native
  symlink execution test is skipped on Windows.
- Targeted backend run: **94 passed, 4 skipped**. Covers launcher, environment
  protection, installer provenance, restart, updates, and Ronin security gates.
  Skips include native POSIX and explicitly gated Mac runtime tests.
- Tenshu: **production build and bundle-size gate passed; 14 frontend security
  tests passed**. The lockfile contains Darwin arm64 bindings for Rolldown,
  Tailwind Oxide, and Lightning CSS.
- Real headless Mado end-to-end test: **passed** when run outside the Windows
  process sandbox. Its initial `spawn EPERM` failure was an environment restriction.
- Changed Python files: Ruff passed. Workflow YAML parsed. `git diff --check`
  passed. The existing local Python environment also passed `pip check`.
- Final full backend suite, including the new shell tests: **1,070 passed,
  9 failed, 6 skipped**, with one pre-existing SQLite worker/event-loop warning.
  All nine failures reproduced on the unchanged baseline.

Broad regressions were run in disposable copies without the operator's `.env`
or application data. An unchanged `git archive HEAD` baseline reproduced the
unrelated failures listed below; its browser failure was resolved by allowing
the isolated Chromium subprocess.

## Existing failures outside this patch

These prevent calling the entire repository test suite green:

| Tests | Observed failure |
| --- | --- |
| `test_smoke::test_version` | Release metadata reports `1.47.101` while the Python/package version is `1.47.94`. |
| `test_smoke::test_schema_upgrade_stamps_legacy_database_before_upgrade` | Migration expectation differs from current stamping behavior. |
| `test_harakiri_runtime::test_exact_telegram_harakiri_takes_emergency_path_and_acknowledges` | Missing `operators` table in the test database. |
| Two `test_mapping_rpa` API tests | HTTP 503 instead of the expected successful response. |
| Two `test_private_transformation_profile_files` API tests | HTTP 503 instead of the expected successful response. |
| `test_samurai_direct_profiles::test_source_semantic_classifier_uses_registered_governed_task_without_legacy_fallback` | Classifier enters the fallback the test rejects. |
| `test_workflow_inspection::test_excel_attachment_can_be_opened_by_server_file_id` | Permission result is blocked instead of success. |

The 1.47.102 / build 253 release preparation subsequently aligned `version.json`,
`pyproject.toml`, and `shogun.__version__`. The version-mismatch test above now
passes. The full-suite counts remain the original audit results; they do not
claim a complete rerun after that metadata correction.

## Remaining macOS verification

The new `.github/workflows/macos-compatibility.yml` runs the actual installer
on macOS 14 and 26 arm64 runners with Python 3.12 and Node.js 22. It then tests
real memory embeddings/persistence, native startup, authenticated setup in
Chromium and WebKit, supervised restart, and backend regressions.

That workflow still needs a passing run against the exact release revision.
It uses GitHub's arm64 runners, not physical M3/M4/M5 devices. Finder launch,
Gatekeeper behavior, Safari itself, macOS privacy permissions, Retina/external
display coordinates, provider credentials, and a real update/uninstall cycle
remain manual checks on a disposable target Mac.

Ronin window listing/focus, native application launch/close and UI control
inspection are not implemented on macOS. Live Office COM/Outlook automation and
the Windows OCR fallback are also unavailable. See [the macOS guide](macos.md)
for installation instructions, capability scope, and the target-Mac checklist.

## Both-edition follow-up

The same installer, launcher, shortcut, and uninstaller corrections were also
applied and tested against the separate `WHITELABEL-Shogun` working tree. White
Label's existing productisation changes, licence gate, and commercial modules
were retained. This is not an environment-variable edition toggle.

The White Label Mac downloader and in-app updater previously referenced the
public Yellow Label repository. They now reference the private White Label
repository, with temporary protected installer authentication. The White
downloader verifies the source edition before copying; both downloaders refuse
to overlay a detected installation of the other edition. `SHOGUN_INSTALL_DIR`
allows selecting a separate installation directory.

Each repository has its own macOS workflow and edition-specific regression
checks. Final Yellow Label checks after adding edition protection: **26 shell
tests passed, 1 skipped; 103 targeted backend tests passed, 5 skipped**. The full
Yellow Label baseline comparison above predates these final edition assertions.
White Label's validation and remaining limitations are recorded in its own
`docs/deployment/macos-audit-2026-09-09.md`.

At audit time, the common root dependencies and frontend lockfiles were equivalent
between the editions (apart from project version metadata), so the Apple Silicon
Python dependency resolution evidence applies to both. Yellow Label release
preparation then upgraded its frontend `js-yaml` dependency from 4.3.1 to 4.3.2
to resolve [GHSA-2883-xcg3-v3hh](https://github.com/advisories/GHSA-2883-xcg3-v3hh),
which blocked the repository's required pre-push security gate. Neither edition has been executed on a
native Mac in this session; both workflows and the physical-Mac checklist remain
release acceptance requirements.

## First native CI run during release preparation

The initial [native run](https://github.com/AlphaHorizon-AI/Shogun/actions/runs/34343868430)
successfully installed the application, Office and Ronin dependencies, Chromium,
and WebKit on macOS 14 and 26 arm64. Both systems passed all 27 shell tests;
macOS 26 also passed the real embedding and persistent-memory roundtrip.

It exposed an MPS model-allocation failure on macOS 14. The embedding loader now
retries that specific failure on CPU while retaining GPU memory safety limits;
unrelated model errors and failed CPU retries still propagate. Four regression
tests cover the normal path, CPU recovery, and both failure cases.

The browser smoke test also mistook the telemetry invitation's heading for a
ready setup form. It now waits for the actual form input, retaining the private
bootstrap URL and JavaScript-error checks. A new CI run must validate both fixes.
