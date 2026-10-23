# eMudhra maintenance — Yellow Label 1.47.119, build 270

This maintenance patch preserves the Yellow Label capability boundary, application data locations, credentials, local approvals and existing user changes. It changes certificate/tooling requirements and update preparation; it adds no database migration or enterprise service.

**Corrected inputs and runtime selection**

Application certifi must be at least 2026.10.19 and pip must be at least 26.2.2. The bootstrap installs exact independently hash-verified wheels, with index access, dependency resolution and caching disabled for that bootstrap. Newer compatible stable releases are retained. [Python guidance](https://discuss.python.org/t/information-for-python-users-regarding-emudhra-emsign-ca-certificate-security-incident/109576).

Supported Node lines are 22.23.4+ on 22.x and 24.22.1+ on 24.x. The selected environment's `node-runtime` directory takes precedence over global Node when present. The shared installer authenticates the complete official Node 24.22.1 archive before extraction. It supports Windows x64, Linux x64/ARM64 and macOS ARM64; other platforms can use their native vendor package. [Node release and signed checksums](https://nodejs.org/en/blog/release/v24.22.1).

Playwright uses the corrected selected Node through `PLAYWRIGHT_NODEJS_PATH`. Its existing package, browser installation and saved profiles are retained. An explicitly configured affected driver is rejected, rather than silently ignored. Direct manual Playwright CLI commands also need this runtime selection; application browser operations and the shipped installers set it themselves.

For the existing Windows checkout, run these commands from the project directory with the intended interpreter:

```powershell
& .\.venv\Scripts\python.exe shogun\security_maintenance.py bootstrap
& .\.venv\Scripts\python.exe scripts\install_security_node.py
& .\.venv\Scripts\python.exe shogun\security_maintenance.py check --node
```

The Node installer is idempotent for an existing compatible application-owned runtime. For a direct Playwright CLI call, set the process-local override first:

```powershell
$env:PLAYWRIGHT_NODEJS_PATH = (Resolve-Path .\.venv\node-runtime\node.exe).Path
& .\.venv\Scripts\python.exe -m playwright --version
```

On Linux, select the actual environment's Python and use the same Python scripts. Normal package downloads require a corrected native store too: pip's Linux truststore backend combines system trust with its vendored bundle. Ubuntu 24.04's incident correction starts at `ca-certificates` 20260816ubuntu0.24.04.1. With a healthy package database, the vendor's targeted route is `sudo apt update` followed by `sudo apt install --only-upgrade ca-certificates`. [Ubuntu guidance](https://ubuntu.com/blog/emudhra-ca-compromise-fixes-available).

Do not blindly repair unrelated interrupted OS package operations as part of an application update. Record the pending packages and coordinate any broader repair. An affected Linux native bundle now fails the application's maintenance prerequisite check even when pip and certifi versions are current.

**Verification**

The read-only prerequisite check uses the explicitly selected interpreter. It checks package floors, Python CA bundles, configured PEM trust paths, effective Linux system trust and selected Node/Playwright versions. It rejects the identified public-root and intermediate certificate anchors without editing private/enterprise CA material. It does not claim complete incident coverage from versions or root names alone.

```powershell
& .\.venv\Scripts\python.exe scripts\verify_security_ci.py --runtime-security
& .\.venv\Scripts\python.exe -m pytest --noconftest -q tests\test_security_maintenance.py tests\test_update_installer.py
& .\.venv\Scripts\python.exe scripts\verify_tls_incident.py --live --output tmp\emudhra-maintenance\live-tls.json
```

The retained public fixture set covers all six TLS intermediates, their alternate chains and the two No-CT diagnostic chains. Hashes and verification times are in `tests/fixtures/emudhra/manifest.json`. Offline tests use a fixed verifier time within each chain's validity; they do not change the machine clock or trust stores. They check both application and pip bundles, plus an isolated original-root positive control that confirms the fixtures reach the trust decision.

The opt-in live command makes credential-free HEAD requests through HTTPX, pip's actual combined trust context and the selected Node runtime. It disables automatic netrc/keyring/auth discovery and does not install anything from a diagnostic host. The current environment had no proxy overrides; another environment requiring a managed proxy needs a separately reviewed diagnostic path and upstream validation evidence. Expiry, hostname mismatch, offline revocation and transport errors remain inconclusive. A failed prerequisite still causes a failing exit even if some probes pass.

**Update and recovery behavior**

The in-app updater requires administrator authorization and corrected tooling before download. Commit resolution must produce a full immutable SHA; there is no moving-branch fallback. Preparation validates Yellow Label metadata and required release files, builds the frontend, installs Python dependencies with the certifi floor, runs `pip check`, and checks the candidate's maintenance policy before copying application files.

The installation worker owns its exclusive lock and temporary build directory. Cancelling the HTTP waiter cannot release that lock or delete a source tree still being used by the worker. The standalone repair updater uses the same preparation/promotion code and stops on failure.

Git installations with local changes stop for review. Do not discard, reset or stash user work automatically to satisfy that check. Freeze the intended source before preparing a release.

Persistent directories and configuration are excluded from promotion: data, environments, vault, configs, logs, scratch, pending state, local instructions and real `.env` files. Frontend dependency caches are also retained. No application migration, database restore, key regeneration, account reset or browser-profile deletion is performed by this patch.

Python dependency installation in an existing environment is not transactional. If it fails, application files are not promoted, but partial dependency changes may remain. Preserve the failure report and repair the environment through corrected tooling. Do not claim that the original environment was fully rolled back.

Before code promotion, the updater retains original application files under `.states/update-backup-*`. A partial copy failure restores previously replaced files and removes newly promoted files. If recovery itself fails, the operation reports that explicitly. This is code recovery material, not an independently verified secure rollback artifact. A fallback must retain corrected Python/Node trust, the current compatible database and the intended data paths. Do not restore an old affected environment or automatically restore an old database snapshot. If a verified secure fallback is unavailable, repair forward.

An interrupted updater can leave `.states/update-install.lock`. Inspect its PID and confirm no updater/worker remains before an operator removes a stale lock. The updater does not guess that a lock is stale and start a second writer.

After a successful update, restart through the original launcher and verify new process/runtime identities and fresh TLS connections. A successful preparation response explicitly leaves activation verification pending. The maintenance implementation itself does not restart a running installation, drain external tasks or open existing user profiles as a test.

**Scope limits**

The PHP runtime RCE advisories CVE-2026-109618 and CVE-2026-109619 are separate from this certificate incident. No PHP application source or Composer manifest was found in this checkout. Existing PHP web workloads elsewhere require their own branch/vendor correction. [PHP advisories](https://www.php.net/).

Container instructions now select corrected Node and bootstrap Python before ordinary dependency installs. Native Docker execution, macOS activation, code-signing verifier paths and other installations require their own recorded results; local Windows checks do not verify those targets.
