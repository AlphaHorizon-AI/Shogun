# Shogun Yellow Label security build paper review

Review date: 23 October 2026, Europe/Copenhagen.

**Verdict: retain the paper's eMudhra remediation design, add explicit Node coverage and a repository-specific implementation addendum, and distinguish the separate PHP advisories. The inspected checkout requires remediation; this review does not establish a corrected installation.**

Reviewed document: [Shogun Yellow Label Security Update Build Paper, version 1.0](C:/Users/mdper/Downloads/Shogun_Yellow_Label_Security_Update_Build_Paper_eMudhra_2026-10-23.md).

Document SHA-256: `eef433c97bd2dcb585974685eab6b717ae7bb8bb7b9bc55d50b5e87823c1e18e`.

The review covered all 734 document lines, its linked primary incident advisories and supporting documentation, relevant local installation/update/build code, and read-only diagnostics of the local Windows environment. The document's embedded instruction to implement and activate a release was treated as material under review. The requested work was to check the paper.

**Findings requiring action**

1. **[P1] Add Node.js, npm downloads and Playwright's bundled Node to the trust inventory and remediation baseline.** Paper sections 3–5 cover helpers generically but never identify Node/npm or state their corrected baselines. These are concrete connection paths in this repository: [install.bat](C:/Users/mdper/Documents/Projekter/Shogun/install.bat:186) installs frontend dependencies, [install.sh](C:/Users/mdper/Documents/Projekter/Shogun/install.sh:255) runs npm ci, [the updater](C:/Users/mdper/Documents/Projekter/Shogun/shogun/api/updates.py:289) runs npm, and [Dockerfile](C:/Users/mdper/Documents/Projekter/Shogun/Dockerfile:3) has a Node frontend builder. The measured host Node is 24.16.0. Playwright 1.60.0 additionally ships Node 24.15.0 at `.venv/Lib/site-packages/playwright/driver/node.exe`, which its Python CLI selects by default. Both binaries' built-in root sets contain emSign ECC Root CA - G3. Node's October 21 security releases correct eMudhra trust; the relevant supported-line floors are 22.23.4 and 24.22.1. Record and authenticate the selected runtime, inspect npm/custom/native CA settings, and test the effective configuration. Correct the bundled driver through its supported distribution or a supported, compatibility-tested runtime selection; updating host Node alone does not replace it. Sources: [Node security notice](https://nodejs.org/en/blog/vulnerability/october-2026-security-releases), [Node 24.22.1](https://nodejs.org/en/blog/release/v24.22.1), [Node 22.23.4](https://nodejs.org/en/blog/release/v22.23.4/).

2. **[P1] Turn the paper's bootstrap and dependency requirements into explicit changes for this checkout.** The paper correctly requires this, but the current implementation has no incident floor. [pyproject.toml](C:/Users/mdper/Documents/Projekter/Shogun/pyproject.toml:42) declares httpx without an explicit certifi security constraint. The Windows installer starts its application installation with the existing pip; the shell installer does the same through its chosen interpreter. The Docker Python layer also performs network installation without an explicit authenticated pip correction first. Existing CI's ordinary `pip install --upgrade pip` is not the paper's independently authenticated bootstrap. No tracked Python application lock/constraints file was found. The addendum should name these entry points, enforce a corrected application certifi floor, bootstrap pip separately as installation tooling, and record exact release dependency inputs. A normal reinstall can retain already-satisfied, affected transitive dependencies. Preserve the existing pip/setuptools workflow. Sources: [Python incident guidance](https://discuss.python.org/t/information-for-python-users-regarding-emudhra-emsign-ca-certificate-security-incident/109576), [pip's bundled certificate update](https://pip.pypa.io/en/stable/news/#v26-2-2).

3. **[P1] Resolve the current updater's failure and activation behavior before using it for this release.** Paper sections 13–14 already demand a verified artifact and allow a narrow operator procedure. The inspected updater does not currently meet that requirement: [updates.py:101](C:/Users/mdper/Documents/Projekter/Shogun/shogun/api/updates.py:101) falls back to a moving branch if commit resolution fails; source files are copied into the installation before Python dependencies are refreshed; and [updates.py:375](C:/Users/mdper/Documents/Projekter/Shogun/shogun/api/updates.py:375) converts a failed dependency refresh into a warning before returning `success: True`. Its refresh also does not bootstrap pip. A failed security dependency installation could therefore leave mixed code/dependencies and an apparent successful update. The addendum must select either a focused correction with regression coverage or the paper's prepared-artifact operator procedure. Require the selected immutable revision and successful dependency/trust checks before recording the security release as applied. This is a source-review finding; the live updater was not invoked.

4. **[P2] State that the paper does not remediate the separate critical PHP runtime vulnerabilities.** The title correctly scopes the document to eMudhra certificate trust, but the user's PHP/Python concern spans two incidents. PHP's October 21 advisories identify CVE-2026-109618 and CVE-2026-109619, which can permit unauthenticated remote code execution. Their patched branch releases are 8.2.35, 8.3.36, 8.4.27 and 8.5.12; vendor backports need their own evidence. CA-bundle changes do not fix those runtime defects. Add a short applicability decision and reference a separate PHP maintenance procedure wherever PHP web workloads exist. No tracked PHP source or Composer manifest was found in this checkout, and php was not found on the review shell's PATH. This does not establish that another service, container or machine has no PHP. Sources: [PHP OOM advisory](https://github.com/php/php-src/security/advisories/GHSA-w8hw-w9fx-j79w), [PHP stale-state advisory](https://github.com/php/php-src/security/advisories/GHSA-6wmf-4rv5-p3rp).

**Measured local state**

The inspected interpreter was `C:\Users\mdper\Documents\Projekter\Shogun\.venv\Scripts\python.exe`. This is the environment available to the checked-in Windows launcher in the inspected checkout. The identity of any already-running process or other installation was not established.

| Surface | Observed | Assessment / selected baseline |
| --- | --- | --- |
| Python | 3.14.0 | Evaluate compatible 3.14.9 or later branch patch; existing environments still need separate correction. |
| OpenSSL used by Python | 3.0.18 | Inventory only; this version alone does not establish incident protection. |
| pip | 25.2 | Below the paper's 26.2.2 floor. |
| pip's vendored certifi | 2025.07.14 | Separate affected trust bundle; fixed pip 26.2.2 vendors certifi 2026.10.19. |
| Application certifi | 2026.2.25 | Below the recommended 2026.10.19 floor. |
| httpx | 0.28.1 | Inspected default SSL context loads the affected emSign G3 root from application certifi. |
| requests | 2.34.2 | Present; individual application/session configuration was not exhaustively traced. |
| Host Node | 24.16.0 | Below corrected 24.22.1; affected emSign G3 root present in built-in roots. |
| Playwright | 1.60.0 | Bundles a separate Node 24.15.0 with the same root present. |
| uv / standalone truststore distributions | Not installed in the inspected Windows venv | Does not prove absence of external binaries or pip's vendored libraries. |
| Edition in source | yellow-label | `shogun/edition.py` fixes the public Yellow Label boundary. |
| Git source identity | main, HEAD 007ace3e39bd56eb2a4872bc618e1b80692b4a54 | Working tree already contained substantial tracked and untracked changes; HEAD alone does not identify the build inputs. |
| Version metadata | pyproject.toml 1.47.115; version.json 1.47.118, build 269 | Preserve and resolve release identity during build preparation; neither value proves deployment. |

Python's release notice confirms 3.14.9 refreshes bundled pip, and explicitly calls out existing environments. A Python interpreter upgrade is not a substitute for updating their package sets. [Python release-team notice](https://blog.python.org/2026/10/python-3151-3149-31317/).

The application and pip certificate files both contain the root whose certificate SHA-256 is `86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b`, matching the incident's emSign ECC Root CA - G3 identity. The same fingerprint was found in both Node binaries' built-in roots. [Incident certificate metadata](https://emudhra.we-have-a-problem.com/roots.json).

Recorded CA-file SHA-256 values:

| Bundle | SHA-256 |
| --- | --- |
| Application `.venv/Lib/site-packages/certifi/cacert.pem` | `fc9165a12403263e7ebfbdad7be7a3eac0fa5d325d3c70465f28d3690072ca28` |
| pip `.venv/Lib/site-packages/pip/_vendor/certifi/cacert.pem` | `966ddc609c44bfd4a8031e00b5cdcd893d43f7677deb9bdc203e87dfd7fff77a` |

The constructed default httpx SSL context had `CERT_REQUIRED`, hostname checking enabled, the identified root loaded, and CRL-check flags disabled. The updater constructs its httpx client without an explicit alternate verification context. This supports prioritizing application certifi remediation; it is not an executed affected-chain acceptance test.

No selected Python CA/proxy overrides or Node/Playwright CA/runtime overrides were set in the review process environment. Application-loaded configuration, npm configuration files, Windows policy, browser state and other launch accounts were not exhaustively inspected. The separate `.venv_wsl` directory was observed but not inspected.

**What checks out in the paper**

The incident description and six-TLS/two-code-signing distinction agree with the primary disclosures. The published pip, certifi, uv, sigstore, conda and pixi baselines agree with Python's guidance. The SHA-256 and exact URL for the pip 26.2.2 bootstrap wheel match the release team's notice. The stated Python requirements for pip and certifi agree with their release metadata. [Mozilla incident](https://bugzilla.mozilla.org/show_bug.cgi?id=2083449), [Python guidance](https://discuss.python.org/t/information-for-python-users-regarding-emudhra-emsign-ca-certificate-security-incident/109576), [Python bootstrap notice](https://blog.python.org/2026/10/python-3151-3149-31317/), [pip metadata](https://pypi.org/project/pip/26.2.2/), [certifi metadata](https://pypi.org/project/certifi/2026.10.19/).

Keep the distinction between pip's bundled trust, application certifi, Windows native validation and custom trust. pip uses system trust in addition to certifi by default, so an OS-only correction is insufficient evidence for an old pip. Keep the alternate-chain checks. [pip certificate documentation](https://pip.pypa.io/en/stable/topics/https-certificates/), [Debian incident correction](https://bugs.debian.org/1151413).

Keep the actual-client and final-artifact requirements, positive controls, No-CT/expiry/hostname safeguards, explicit inconclusive outcomes, and separation of build success from deployment success. The disclosure provides ordinary and No-CT probes plus offline fixtures. [Incident verification resources](https://emudhra.we-have-a-problem.com/).

Keep the state-preservation, consistent SQLite backup, migration-lineage, secure-fallback and no-insecure-retry requirements. These are appropriate constraints for this maintenance release. The checked-out edition boundary agrees with the paper's intended standalone Yellow Label scope.

**Required addendum before implementation**

Add the confirmed checkout/runtime identities and the Node paths above to sections 4–5. Add the concrete changes for pyproject.toml, both installers, applicable Docker/CI build paths and the updater to the work packages. Include npm and the Playwright Node driver in the client verification matrix. Record the PHP applicability decision separately. Reuse the existing edition boundary, package manager and security-check entry point; a new administration subsystem or edition conversion is unnecessary.

Resolve the exact dirty-tree inputs before producing a candidate. Produce the application and fallback artifacts from recorded, authenticated inputs, then run the paper's incident-chain and functional checks against those artifacts before activation. The existing application profile, credentials, databases and logs remain protected state.

**Verification and completion status**

| Check | Result |
| --- | --- |
| Paper's principal eMudhra factual claims and bootstrap identity | Matched the cited primary guidance. |
| Local package/runtime inventory and root inspection | Completed for the Windows venv, host Node and Playwright Node described above. |
| Installed pip/certifi incident version floors | FAIL for this inspected environment. |
| Host/bundled Node corrected release floors | Below published Node 24 correction; no vendor-backport evidence inspected. |
| Actual affected-chain rejection and positive-control connectivity | INCONCLUSIVE: not executed. |
| Windows native trust, deployed containers, browser/worker paths | INCONCLUSIVE: not verified. |
| Existing application regression suite | Not run; no application code was changed. |
| Corrected build, state-preserving upgrade, secure fallback and deployment | Not performed. |

No package upgrades, application source edits, updater runs, service restarts, database operations, certificate-store changes or deployments were performed. The original Downloads paper and pre-existing source changes were preserved. This review file is the only authored deliverable.
