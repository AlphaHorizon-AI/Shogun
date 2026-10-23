# Shogun Yellow Label — Security Update Build Paper
## eMudhra / emSign Certificate Trust Remediation

| Document field | Value |
| --- | --- |
| Document ID | SHOGUN-YL-SEC-2026-10-EMUDHRA |
| Version | 1.6 |
| Prepared for | Michael Peric / M37 |
| Date | 23 October 2026 — Europe/Copenhagen |
| Priority | Urgent security maintenance |
| Product | Shogun Yellow Label, with the installed edition preserved |
| Audience | Coding agent, maintainer and authorized installation operator |
| Status | Security release 1.47.119 / build 270 merged through PR #85; live Windows activation, updater restart and preservation verified; activation follow-up fixes covered by 688 passing backend regressions |
| Evidence | Incident guidance rechecked on 23 October 2026; supporting documentation consulted on 22–23 October |
| Deliverable | Focused patch, rebuilt Yellow Label artifacts, verification evidence and local deployment/recovery procedure |

## 1. Required outcome

Deliver a standalone Shogun Yellow Label maintenance release that rejects the compromised eMudhra certificate chains on applicable connection paths, retains legitimate connectivity, and preserves the installation's existing functionality and data.

Follow the correction through development, build, installation, update and running processes. A successful package upgrade in the developer's terminal is an intermediate result.

The completed work must:

1. Establish the actual Yellow Label revision, edition configuration and execution environments.
2. Authenticate the tools used to obtain the security correction.
3. Correct every effective system, bundled and custom trust source in scope.
4. Update dependency declarations, locks and environment-creation procedures.
5. Rebuild the relevant installer, environment, executable or container.
6. Verify affected-chain rejection and required legitimate behavior.
7. Activate the exact tested Yellow Label artifact.
8. Preserve local state, credentials, permissions and existing logs.
9. Provide a compatible rollback artifact that retains the security correction.
10. Record build and deployment outcomes separately.

Reuse the existing architecture, package manager and release process. Keep the implementation small enough to maintain as part of Yellow Label.

## 2. Yellow Label scope and evidence boundaries

### 2.1 Preserve the product boundary

The user's edition decisions distinguish standalone Yellow Label from White Label capabilities. Earlier Yellow Label SkillOpt material also specifies local improvement and validation without enterprise publication or synchronization. That material is a proposed design, not proof that every described feature is implemented. [P1], [P2]

| Area | Requirement for this security release |
| --- | --- |
| Shogun / Tenshu core | Correct the actual local runtime and its network clients. |
| Agents, tool connectors and model routing | Preserve the edition-permitted features and configurations actually installed. |
| ToolGate and local approval rules | Preserve existing enforcement, permissions and emergency controls. |
| Local SkillOpt, skills, memory and benchmarks | Preserve implemented state and behavior; do not implement missing proposed features as a dependency of patching. |
| Flow Stack, Team Mode and Microsoft Teams integration | Do not introduce White Label features through this update. |
| Nexus and Gensui | No new installation, registration, connectivity or reporting dependency. |
| Extended Logs product interface and enterprise reporting | No requirement to add the White Label interface or centralized audit services. |
| Existing local logs or immutable audit | Preserve what is actually implemented, including any required integrity keys. |
| Enterprise skill publication, registry, approval and synchronization | Outside the standard Yellow Label maintenance scope. |
| Branding and edition configuration | Preserve the existing Yellow Label identity and entitlement behavior. |

Local ToolGate approvals remain applicable. Excluding an enterprise approval workflow does not remove an existing local security control.

Where shared source implements multiple editions, use the current capability boundaries and edition-specific build configuration. Do not create a new fork or rewrite the licensing system merely to ship this correction.

### 2.2 Classify the target before applying an artifact

Record one of the following descriptive installation profiles. These are report categories, not proposed runtime configuration values.

| Observed profile | Handling |
| --- | --- |
| Standard Yellow Label | Apply the compatible Yellow Label maintenance release. |
| Legacy-full installation with retained historical modules | Preserve existing modules and data; assess active trust paths separately and use a compatible core release. |
| Completed White Label installation | Use the matching White Label/general Shogun remediation procedure; do not downgrade it under this paper. |
| Incomplete or inconsistent edition conversion | Preserve state and resolve the code/database/edition mismatch before activation. |

The user previously discussed historical installations retaining frozen Gensui/Nexus modules. Their presence must not trigger deletion as “Yellow Label cleanup.” Determine whether retained modules actually run or make network connections. A frozen feature policy does not establish that an active client's trust is safe. [P2]

### 2.3 What is verified and what is not

External advisories establish the incident and corrective release baselines. The earlier general Shogun paper supplies the remediation structure. User context supplies edition boundaries and the relevance of a Windows laptop installation. [P2], [P3]

This paper does not establish the current repository, branch name, Python version, dependency manager, UI framework, database location, updater implementation or completed CI setup.

A previous Yellow Label-to-White Label troubleshooting discussion included a migration-lineage problem. It is background for the guard in section 6, not a currently reproduced defect or evidence that every Yellow Label installation has that problem.

Do not infer implementation from a previous build paper. Discover the current code and installation before selecting paths or commands.

## 3. Incident and operational implications

Mozilla independently confirmed eight compromised eMudhra intermediate CA private keys: six for TLS and two for code signing. The incident resulted from defective key generation. [S2]

An attacker able to intercept a connection could exploit a client that accepts an affected chain. This evidence does not establish a compromise of Shogun or the user's laptop. Exploitation of clients that do not enforce Certificate Transparency remains unknown. [S4], [S5]

Python's security guidance identifies relevant ecosystem updates. The correction must reach the clients that actually make network connections. [S1]

| Connection path | What must be established |
| --- | --- |
| Model-provider and tool HTTPS | Actual HTTP client, verification implementation and certificate sources. |
| pip / dependency installation | Installer's bundled trust, additional native trust and selected package sources. |
| Updater / Git / release download | Downloader, transport authentication, artifact identity and verification behavior. |
| Separate agents or background workers | Whether they use the main runtime or another environment. |
| Embedded browser or native helper, where present | Its own update and trust mechanism; a backend change is insufficient evidence. |
| Packaged application / installer | Embedded runtime, certificates, libraries and bootstrap behavior. |
| Container or Linux service, where supported | Relevant host, builder, runtime and mounted certificate configuration. |
| Artifact signature checking, where used | Code-signing verifier and applicable vendor remediation. |

Modern pip can combine certifi with system trust. An application's HTTP client may use a different bundle or verifier. [S6] Alternate cross-signed chains also matter: Debian's correction addresses emSign ECC Root CA - G3 and Comodo AAA Services root paths; the latter root's own key is not thereby shown to be compromised. [S7]

ToolGate authorization and local audit records remain useful controls. They do not establish the identity of a remote TLS endpoint.

## 4. Remediation baseline

Recheck current maintainer notices at implementation time. These are incident floors, not a reason to install unused tools or upgrade all unrelated packages.

| Component, when present | Baseline | Required handling |
| --- | --- | --- |
| pip | 26.2.2 or a later compatible corrected release | Include each relevant existing environment and bootstrap copy. [S8] |
| Application certifi | 2026.10.19 or a later compatible corrected release | Python recommends .19; the earlier .18 advisory entry is not the selected compatibility baseline. [S1], [S3] |
| Node.js host / npm / build runtime | 22.23.4+ on 22.x or 24.22.1+ on 24.x | Preserve supported major lines; authenticate runtime artifacts and verify effective native/custom trust. [S24] |
| Playwright Node driver | Corrected Node runtime meeting the same supported-line baseline | Inspect the actual driver; correct through the supported package or tested runtime override, and verify browser compatibility. [S24] |
| uv | 0.13.4 or a later compatible corrected release | Include all binaries used by installation, builds and updates. [S9] |
| sigstore | 4.5.1 or later | Only where actually used. [S1] |
| conda | 26.9.4 or later | Only where actually used. [S1] |
| pixi | 0.82.1 or later | Only where actually used. [S1] |
| OS/platform trust | Vendor-specific correction | Record applicable vendor evidence and the target's resulting state. |
| Custom CA files and native clients | Configuration-dependent | Verify the effective trust decision for each materially different path. |

The Python release team published 3.15.1, 3.14.9 and 3.13.17 with refreshed bundled pip. Select a supported patch for the relevant branch; do not move Yellow Label to a new minor version without compatibility evidence. Existing virtual environments still require attention. [S10]

pip 26.2.2 requires Python 3.10 or later; certifi 2026.10.19 supports Python 3.7 or later. An older interpreter cannot be marked safe merely because the new pip is incompatible. Use an evidenced distributor correction or a supported runtime migration. [S11], [S12]

Pin exact release inputs and record hashes or equivalent authenticated identifiers. A documented vendor backport may satisfy the correction when its identity and behavioral evidence are recorded. Compare package versions using ecosystem rules, not lexical string ordering.

## 5. Phase A — Discover the actual installation

### 5.1 Source, edition and launch identity

Before mutation, record:

- Repository and redacted remote identity.
- Selected branch/tag, exact commit and local changes.
- Installed edition and effective capability configuration.
- Updater channel and intended replacement artifact.
- Actual launcher, shortcut, service or packaged executable.
- Working directory, user/service account and application data locations.
- Python/runtime identity and separate worker environments.
- Dependency manifests, locks, build scripts and installer inputs.

Do not assume the repository is named “Yellow Label,” its branch is `main`, or a checkout's default configuration selects the installed edition.

Use `rg` or indexed search to inspect the relevant code. Read project instructions and scripts before executing them. Avoid printing credential-bearing remote URLs or complete environment dumps.

### 5.2 Environment and trust inventory

Create one record for each distinct target or client configuration.

| Surface | Record |
| --- | --- |
| Main application | Runtime path, version, dependencies, CA configuration and process identity. |
| Separate workers / jobs | Their interpreter or image, launch settings and active network paths. |
| Existing virtual environments | Exact pip, certifi and other package-tool identities. |
| Fresh installation | Interpreter source, seeded installer and first network dependency operation. |
| Updater | Actual downloader, certificate backend, repository/release channel and artifact selection. |
| Windows native clients | Whether verification uses Windows APIs and relevant policy/store scope. |
| Python/OpenSSL clients | Effective CA material and explicit SSL contexts. |
| Embedded executables | Bundled runtime, libraries and CA data; update owner. |
| Linux/macOS/container targets | Only supported or deployed profiles actually found. |
| Custom certificates / proxy | Whether trust is replaced or supplemented, and who validates the upstream endpoint. |

Inspect relevant overrides such as `SSL_CERT_FILE`, `SSL_CERT_DIR`, `REQUESTS_CA_BUNDLE`, `CURL_CA_BUNDLE`, `PIP_CERT` and uv certificate settings. Record selected redacted values only. uv's native/custom trust behavior must be assessed on its own terms. [S13]

Absence of a component can justify NOT_APPLICABLE. Inability to inspect it means INCONCLUSIVE.

### 5.3 Windows diagnostic template

First establish the interpreter used by Yellow Label's real launcher. The following path is an example to replace, not an assertion about the installation.

~~~powershell
$ylPython = 'C:\path\to\Shogun\.venv\Scripts\python.exe'

& $ylPython --version
& $ylPython -m pip --version
& $ylPython -m pip show certifi
& $ylPython -c "import sys, ssl; print(sys.executable); print(ssl.OPENSSL_VERSION); print(ssl.get_default_verify_paths())"
~~~

Where certifi exists:

~~~powershell
& $ylPython -c "import certifi; print(certifi.__version__); print(certifi.where())"
~~~

Virtual environments have their own package sets; Windows environments conventionally contain their executable under `Scripts`. Their precise directory must still be discovered. [S17]

Do not substitute whichever executable `python`, `pip` or the `py` launcher currently selects. For an embedded application with no supported standalone Python entry point, use its supported inspection/build mechanism.

These commands provide inventory evidence. They do not prove affected-chain rejection.

## 6. Preserve local state and database compatibility

### 6.1 Protected-state inventory

Locate and preserve the actual implementation of:

- User accounts, permissions and local authentication state.
- Provider/API credentials, token references and installation encryption keys.
- Conversations, archives, memories, indexes and knowledge files.
- Agent configuration, model routing, tool permissions and security postures.
- Local skills, versions, quarantine and benchmark state where implemented.
- Edition-permitted workflows, schedules and pending task state.
- Application databases, configuration and custom certificates.
- Existing operational logs, audit history and integrity keys where used.
- Edition settings, release-channel configuration and managed launchers.

These are discovery and preservation categories, not claims that all features exist in every Yellow Label release.

Keep runtime files distinguishable from persistent user state. Do not delete the installation directory to obtain a clean environment, reset accounts, regenerate keys or replace configuration with defaults.

If credentials depend on the operating-system user or service identity, preserve that identity or use the established credential-migration mechanism. Verify usability without exposing the secret values.

### 6.2 Obtain recoverable state

Use the application's supported backup procedure and verify that the recovery material is usable. Protect secrets and user content with the existing access controls.

For SQLite, use a supported consistent backup method, such as its backup API. A blind copy of a live database is not the required method. SQLite's backup API creates a snapshot; WAL-mode state may also reside outside the main database file. [S21], [S23]

Do not delete journal/WAL files as cleanup or treat a copy of only the main file as automatically complete. Where files, indexes and databases must be consistent together, coordinate the snapshot or stop the relevant writers according to the existing procedure.

Backups are recovery material. Ordinary application rollback should retain current compatible user data, as specified in section 15.

### 6.3 Migration-lineage guard

This certificate maintenance release should not require a new application schema. Separate unrelated feature migrations from the patch.

Before any launcher or updater can trigger migrations, establish:

1. The code revision belongs to the intended Yellow Label release.
2. Its expected migration graph is understood.
3. The existing database is on a compatible lineage.
4. A replacement environment will use the same intended database path.
5. The application will not silently create a new empty database.

If an unexpected revision, unresolved branch conflict or incomplete edition conversion appears, preserve the database and diagnostics and stop activation of the incompatible artifact.

Do not delete the database, stamp revisions, merge migration heads blindly, switch a command from `head` to `heads` merely to suppress an error, or import White Label migrations.

Multiple heads are not universally invalid; Alembic supports branching. The requirement is consistency with the project's intended graph and a reviewed transition. [S22]

Do not resume an earlier Yellow Label-to-White Label conversion under this security-update task. Complete unaffected build work and report the blocked installation accurately.

## 7. Phase B — Establish an authenticated update path

### 7.1 Bootstrap before ordinary dependency downloads

Use a trusted administrative/build environment to obtain authoritative guidance and expected artifact identities. Correct platform trust through its supported route.

Where the target's TLS verification may still be affected, authenticate the bootstrap artifact using an expected digest obtained independently through a trusted channel. Fetching a checksum next to a file through the same affected path is insufficient.

If evidence suggests the local host itself has been compromised, preserve evidence and use trusted recovery. The following procedure assumes the local interpreter and installer can execute reliably.

### 7.2 Exact pip bootstrap artifact

The Python release-team notice publishes this wheel and SHA-256 value. Reconfirm them through the trusted source at implementation time. [S10]

~~~text
pip-26.2.2-py3-none-any.whl
SHA-256: fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70
~~~

Use this bootstrap only where the installer needs correction. If the target already has a newer compatible release with verified protection, retain it and record its identity instead of downgrading mechanically to 26.2.2.

For a compatible application-managed Windows environment requiring this bootstrap, after resolving `$ylPython`:

~~~powershell
& $ylPython -m pip --disable-pip-version-check --no-cache-dir install --no-index --no-deps --upgrade "pip @ https://files.pythonhosted.org/packages/3f/06/3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/pip-26.2.2-py3-none-any.whl#sha256=fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70"

if ($LASTEXITCODE -ne 0) {
    throw 'pip bootstrap failed; stop the update and inspect the error.'
}
~~~

For other platforms, use the same exact artifact with the identified target interpreter through the platform's supported procedure.

Keep certificate verification enabled. Do not append `--trusted-host` or force an incompatible interpreter with `--ignore-requires-python`. Follow distributor ownership rules for OS-managed Python; do not use `--break-system-packages` to force this recipe globally.

### 7.3 Offline alternative

If the target cannot safely retrieve the wheel:

1. Obtain it in the trusted environment.
2. Verify its digest against the independently authenticated expected value.
3. Transfer through the existing authorized channel.
4. Recompute the digest on the target.
5. Install only the verified local file, with index access and dependencies disabled.
6. Confirm the resulting executable and pip version.

After successful digest verification, the Windows installation form is:

~~~powershell
& $ylPython -m pip --disable-pip-version-check install --no-index --no-deps --upgrade 'C:\approved-staging\pip-26.2.2-py3-none-any.whl'

if ($LASTEXITCODE -ne 0) {
    throw 'Local pip bootstrap failed; stop the update.'
}
~~~

The directory is illustrative. Use the actual protected staging location.

The pip wheel digest authenticates that wheel. It does not authenticate subsequent packages or repair every CA source. Establish corrected trust before ordinary online dependency resolution, or use a separately authenticated complete offline artifact set.

### 7.4 Other tools and fresh environments

Update uv and other discovered tools through their supported installation owner or authenticated release artifacts. Switching to native trust is valid only when that platform's effective trust is corrected.

Repair new-environment creation as well as existing environments. An old interpreter or seeding cache can recreate an affected installer. Ensure the first network install uses authenticated corrected tooling.

Do not run a broad script that updates every Python environment on the laptop. Resolve and update the environments owned by this release.

## 8. Phase C — Correct effective trust

### 8.1 Windows native validation and Python validation

Windows distributes trusted and untrusted certificate lists through CTL update mechanisms. Those update paths can be disabled or redirected by policy. Record the effective configuration and relevant verification result; a generic “Windows is up to date” statement is insufficient. Respect the existing organization-managed distribution route. [S18]

The incident responders report Windows blocking of the affected certificates through native trust mechanisms. This does not establish the state of an individual laptop or every application on it. [S5]

Python's `ssl` module uses OpenSSL. The truststore library's Windows backend uses CryptoAPI. [S19], [S20] The implementation consequence is that importing certificates from Windows into an OpenSSL context must not be assumed equivalent to using Windows' native verification policy.

For each Yellow Label client, establish the actual backend and CA sources. Test the application path even when a browser or native Windows client already rejects the chain.

If an offline native-store mitigation is necessary, use the established administrative route and an explicitly reviewed, fingerprint-verified set of affected certificates. Do not run a downloaded incident-response script blindly, relabel community tooling as Microsoft software, or replace enterprise certificate policy wholesale.

Prefer corrected dependencies and supported configuration. If a specific adapter requires native trust integration, use a supported explicit SSL context where practical and test it. Do not introduce a global SSL monkey-patch as a universal remedy.

### 8.2 Application, bundled and custom certificates

Correct application certifi separately from pip's vendored copy. Inspect copied PEM files, embedded bundles, installer resources and mounted custom certificate directories.

Determine whether each configured source replaces or supplements other trust. Preserve legitimate private/enterprise roots while correcting inherited public-root content.

For a TLS inspection proxy, distinguish the application-to-proxy trust decision from the proxy's validation of the remote server. A proxy-issued certificate seen by Yellow Label does not demonstrate that the original affected chain would be rejected upstream.

A root-name search is inventory evidence. A retained root can coexist with an effective intermediate block, while removal of one root can leave an alternate chain available. Verify behavior.

### 8.3 Dependency resolution and caches

Update the actual declarations and lockfiles through the existing package manager. Keep unrelated upgrades out of the patch unless required for compatibility.

For a pip hash-checked installation, pin and authenticate the complete dependency closure, including transitive requirements. One top-level hash is not sufficient. [S14]

Account for build isolation, temporary environments, cached wheels, downloaded installers and environment templates. Invalidate the relevant stale inputs without purging unrelated user files or caches.

Do not edit installed third-party packages manually as the normal remedy. Preserve the ability to recreate the correction from recorded source and authenticated inputs.

### 8.4 Other supported platforms

For Linux/macOS installations and container images actually in scope, use the relevant vendor correction. Do not treat Debian package versions as universal Linux version floors.

Correct relevant builders and final runtimes. Revisit pinned base-image digests deliberately; a rebuild cannot select a different base while the old digest remains fixed. Docker's pull and no-cache controls address different parts of this process. [S15]

## 9. Build corrected Yellow Label artifacts

### 9.1 Preserve the release identity

Build from the recorded commit using the intended Yellow Label configuration. Record exact dependencies, runtime, package-tool versions and final artifact hash/digest.

Inspect release scripts for accidental selection of a White Label repository, package source, edition flag, migration set or installer. A compatible shared-core fix should remain compatible with Yellow Label's established capability boundaries.

Verify that dependencies imported at startup are available in the Yellow Label artifact. Do not solve a missing optional enterprise import by enabling the enterprise feature.

### 9.2 Windows environments and packaged applications

Rebuild the application-managed environment or package through the supported process. Preserve the application's user-data location and installation identity.

Python virtual environments are not generally portable directories. Build a replacement at its intended stable location or use the project's supported relocation/recreation procedure; do not assume renaming or copying an arbitrary environment preserves its embedded paths. [S17]

For a frozen executable or embedded Python installation, rebuild the artifact that contains the affected libraries and CA files. Updating a separate global Python does not update the shipped executable.

Keep the active installation available until the candidate passes its checks. Avoid replacing files underneath a running process unless the existing updater explicitly supports that operation.

### 9.3 Fresh install, existing install and fallback

Validate three relevant paths:

1. A fresh Yellow Label installation using the supported installer.
2. An existing Yellow Label installation with preserved state.
3. A compatible fallback retaining corrected trust.

Use synthetic or designated test data. Do not use a fresh empty profile as the only test of an upgrade.

If containers are a supported profile, verify the final image and running container separately, including mounted CA files and persistent storage. Do not introduce containerization as a prerequisite for patching a desktop installation.

## 10. Preserve runtime behavior and local controls

### 10.1 Restart and new connections

Identify all processes that retain old code or TLS contexts, including background workers actually present. Safely drain or pause their work and restart the required processes after activation.

Evidence must include new TLS handshakes from the selected runtime. An already established connection does not prove the new certificate configuration was loaded.

For in-flight work, preserve pending state and distinguish completed external effects from safe retries. Prevent duplicate workers or duplicate execution after restart.

### 10.2 Functional checks

Use existing tests and a small set of representative smoke checks:

- Start through the real launcher and confirm the original user profile/data.
- Load an existing conversation, local skill and configuration where present.
- Confirm stored credentials remain usable without exposing them.
- Exercise a representative model/tool connection through its actual client.
- Confirm ToolGate permissions, local approvals and stop controls remain effective.
- Check a separate worker or scheduled path if implemented.
- Confirm the update status and existing logging path remain usable.
- Restart again and verify that the correction and state persist.

Use controlled test endpoints or existing designated accounts where suitable. A certificate check does not require sending real messages, modifying external records or running a paid model workload.

### 10.3 Fail clearly

TLS rejection must not trigger `verify=False`, an unverified SSL context, hostname-check disabling, insecure curl/Git options, uv insecure-host configuration or an automatic downgrade.

Present a useful redacted error through the current application mechanism. Do not transform a transport failure into an apparently successful task, erase pending work or alter provider routing silently.

If a legitimate endpoint breaks because it uses an affected chain, correct that endpoint through its operator. Preserve verification and contain the affected connector while the issue remains unresolved.

## 11. Verification design

### 11.1 Incident fixtures and real clients

The disclosure supplies affected intermediate/cross-sign metadata and certificate-chain fixtures. Obtain them as data through a trusted path, retain their provenance and hashes, and inspect the supplied instructions. [S5], [S16]

Cover all six affected TLS intermediates and applicable alternate chains for the public trust configurations in scope. A synthetic untrusted certificate is useful for testing policy but does not replace the actual incident-chain cases.

Do not add a fixture root to a trusted store simply because the fixture includes it. Account for additional defaults, cached intermediates and native policy.

Record the exact client, artifact, effective trust, chain, hostname, purpose, validation time, expected result, observed result and error reason.

Map offline verification to the actual application implementation. An OpenSSL command alone does not prove how Windows CryptoAPI, an embedded browser or a different SDK behaves.

### 11.2 Validity, CT and proxies

Verify that a negative test can reach the intended certificate-validation decision. Expiry, an unrelated hostname mismatch or malformed input can otherwise produce a misleading rejection.

For historical fixtures, use an isolated verifier's supported fixed-time option where needed and document it. Do not change the production system clock.

The disclosure includes both ordinary and No-CT diagnostic chains. A rejection solely because Certificate Transparency is required establishes that policy's behavior; it does not establish that the affected CA has been distrusted. Select complementary fixtures without weakening production policy. [S5]

Check the presented chain when a corporate proxy intercepts TLS. If the proxy replaces it, obtain appropriate upstream-validation evidence or record the unresolved coverage. Do not bypass organizational network controls.

### 11.3 Positive controls and error classification

Use legitimate positive controls with the same client and trust configuration. Test required private certificates separately where relevant.

| Result observed | Interpretation |
| --- | --- |
| Suitable affected chain rejected for expected trust/distrust reason | PASS for that case |
| Affected chain accepted | FAIL |
| Required legitimate endpoint fails because of the correction | FAIL for compatibility |
| DNS error, timeout, connection refusal or proxy network denial | INCONCLUSIVE |
| Expired/malformed fixture or unrelated hostname mismatch | INCONCLUSIVE for incident rejection |
| Only CT rejection, without the necessary complementary trust evidence | Incomplete incident-trust coverage |
| HTTP error or package-not-found after successful TLS | Not evidence of certificate rejection |
| Version, bundle filename or browser result only | Inventory/other-client evidence |
| Test used a different runtime, user or artifact | Invalid for the intended target |

Optional live diagnostic probes must be credential-free and limited to the identified service. Prevent automatic credential discovery from netrc, client configuration, cookies, environment variables or proxy settings. Do not install packages from the diagnostic host.

### 11.4 Keep verification focused

Exercise each release-critical client and materially different certificate configuration. Do not require duplicate tests for identical paths without a concrete reason.

Do not label a native implementation verified because its roots resemble those in a tested PEM file. Where equivalent coverage cannot be established, retain the gap as INCONCLUSIVE.

This is an incident-specific release check, not a claim of a complete security audit.

## 12. Acceptance matrix

| ID | Check | Acceptance criterion |
| --- | --- | --- |
| Y01 | Edition identity | Source, build configuration, installed edition and release channel remain the intended Yellow Label profile. |
| Y02 | Standalone operation | Remediation and application startup require no new Gensui, Nexus or enterprise service. |
| Y03 | Runtime identity | Tests use the actual launcher/runtime and separate workers found in scope. |
| Y04 | Authenticated bootstrap | Selected update tools and artifacts have recorded integrity evidence. |
| Y05 | Applicable versions | Tool/bundle baselines or evidenced equivalent corrections are satisfied. |
| Y06 | Effective trust | System, bundled, custom and native verifier paths are accounted for. |
| Y07 | Incident chains | Applicable affected and alternate chains are rejected for valid reasons. |
| Y08 | Legitimate connectivity | Required public/private endpoints work under the approved verification policy. |
| Y09 | Failure behavior | No insecure retry, hidden success or silent routing change occurs. |
| Y10 | Local controls | Existing permissions, ToolGate behavior, approvals and stop controls are preserved. |
| Y11 | Persistent state | Existing accounts, conversations, memory, skills and configuration remain available where implemented. |
| Y12 | Secrets and audit keys | Existing credentials remain usable and historical integrity remains verifiable where implemented. |
| Y13 | Database lineage | Intended database identity and compatible migration state are preserved. |
| Y14 | Task lifecycle | Restart does not create duplicate workers, lose pending state or blindly repeat external effects. |
| Y15 | Fresh install | New environments cannot reintroduce affected bootstrap/tooling material. |
| Y16 | Final artifact | The shipped installer/environment/executable/image contains the verified correction. |
| Y17 | Activation | Running revision, artifact, configuration and new handshakes match the evidence. |
| Y18 | Secure fallback | A compatible Yellow Label fallback retains corrected trust and current user data. |
| Y19 | Local evidence | Results and deployment status are available without an enterprise reporting dependency. |
| Y20 | Conditional paths | Legacy modules, other platforms and code-signing verification are assessed when present, otherwise marked inapplicable with reasons. |

A known failure is FAIL. A required gap is INCONCLUSIVE. Absence is NOT_APPLICABLE only when evidenced.

## 13. Minimal retained verification and evidence

Extend the existing check/test entry point or add one small command. It should support read-only inventory and verification, accept an explicit target, redact secrets and emit structured results.

Keep remediation actions separate. Do not build a new administration subsystem or add an extended Logs interface for this release.

The following is an unfilled report shape, not completed evidence:

~~~json
{
  "schema_version": 1,
  "incident_id": "SHOGUN-YL-SEC-2026-10-EMUDHRA",
  "verified_at_utc": null,
  "installation_profile": null,
  "installed_edition": null,
  "source_revision": null,
  "artifact_digest": null,
  "runtime_reference": null,
  "data_location_reference": null,
  "migration_state_reference": null,
  "clients": [],
  "preservation_checks": [],
  "checks": [
    {
      "id": "Y07",
      "result": "INCONCLUSIVE",
      "reason": "Not executed",
      "evidence_reference": null
    }
  ],
  "build_result": "INCONCLUSIVE",
  "deployment_result": "INCONCLUSIVE",
  "limitations": []
}
~~~

Use protected identifiers instead of secret-bearing paths/URLs in shared reports. Detailed evidence can remain locally protected with references in the release manifest.

Apply a focused gate in the actual pipeline: freeze inputs, build, test the artifact, produce its manifest, then permit activation. If no CI exists, supply a reproducible operator command for this release. Do not describe a proposed pipeline as already implemented.

A required failed or inconclusive check must produce a failing verification exit status. Keep fixture/version policy maintainable and reassess it when the runtime, trust settings or packaging changes.

## 14. Yellow Label updater and deployment

### 14.1 Select and freeze the release

Discover whether the updater uses Git, release archives, a package manager or another mechanism. Preserve the intended Yellow Label channel and any required authentication.

If it follows a branch, select an exact commit before building. Do not fetch a different moving-branch revision after testing and activate it under the previous result.

Capture intended local changes before preparing a clean build. Do not use destructive Git cleanup to erase them. Avoid writing tokens into remote URLs, logs or release manifests.

Correct the updater's own trust and bootstrap environment. Repairing the application alone does not establish that the process constructing its next environment is safe.

### 14.2 Activate a prepared artifact

| Stage | Required action |
| --- | --- |
| Prepare | Record edition/source/runtime/data identities and usable recovery material. |
| Build | Produce corrected Yellow Label release and compatible fallback. |
| Validate | Complete required trust, persistence, migration and functionality checks. |
| Pause | Prevent concurrent updater runs and safely drain relevant work. |
| Activate | Select the exact tested artifact while preserving configuration and data. |
| Restart | Start through the intended launcher/account and establish new connections. |
| Verify | Compare actual running identity and state with the manifest. |
| Resume | Re-enable paused work/update mechanisms and record the outcome. |

Provide a narrow operator-assisted procedure if the current updater cannot guarantee that transition. A general updater redesign should not delay the focused correction.

Do not automatically switch repositories, import White Label assets, complete an edition conversion or roll an already converted installation back to Yellow Label.

Record inaccessible installations as unverified. A local artifact test is not a deployment result for another laptop or customer environment.

## 15. Secure rollback and recovery

Prepare a known-good Yellow Label application revision rebuilt with compatible corrected trust, installer and runtime inputs. Verify it against the database schema and state expected at rollback time.

Keep the existing user-data locations, accounts and required keys. Do not use a White Label artifact as the fallback for Yellow Label.

Ordinary application rollback must preserve current compatible data. Automatically restoring an old database snapshot may discard conversations, settings, tasks and audit events created after it. A database restore requires a separate concrete recovery decision and loss assessment.

After rollback, confirm:

- Correct edition, source/artifact and launcher.
- Original intended database and user-data locations.
- Credential usability and existing audit integrity where implemented.
- Compatible schema/migration state.
- New TLS connections using corrected trust.
- No duplicate workers or unintended task replay.
- Accurate local update/recovery status.

If no secure compatible fallback exists, contain the failing path and repair forward. Do not automatically restore a known affected image or certificate bundle because a health check fails.

## 16. Local records and incident handling

Use existing Yellow Label operational/audit facilities where present. If they are insufficient or absent, a protected local release manifest and verification report provide the maintenance evidence.

Do not assume the extended Logs product, immutable logging, a specific retention period or an HMAC schema is installed. Preserve whatever history and integrity mechanism exist.

Record the operator, target, incident ID, before/after input identities, source revision, artifact, checks, activation/recovery outcome and unresolved issues. Exclude API keys, passwords, private keys, conversation contents and sensitive tool payloads.

Use accurate states: update required; applied with verification pending; verified for the recorded target; failed; or incomplete. Do not label an installation “fully secure” or “never compromised.”

If actual compromise evidence emerges, preserve observations and handle it as a separate incident. Stop using a suspect host as a trusted release source, establish a trusted recovery path and assess relevant credential exposure. An affected package version alone does not prove compromise; successful patching does not disprove past compromise.

## 17. Work packages and completion gate

| Package | Work | Deliverable |
| --- | --- | --- |
| WP1 | Discover edition, runtimes, trust and protected state. | Inventory and focused change map. |
| WP2 | Authenticate bootstrap and correct effective trust/tooling. | Integrity evidence and exact selected inputs. |
| WP3 | Update manifests, locks, creation and packaging paths. | Focused patch and reproducible build inputs. |
| WP4 | Build release and compatible secure fallback. | Yellow Label artifacts and manifest. |
| WP5 | Run required incident and application checks. | Acceptance results and evidence. |
| WP6 | Resolve update/activation steps for the target. | Operator runbook and actual deployment result. |
| WP7 | Retain small verification gate and documentation. | Repeatable check command and recovery procedure. |

Parallelize discovery and test design where useful. Coordinate edits to shared locks and release state; only one process should activate an installation.

Completion requires:

- [ ] Intended Yellow Label profile and capability boundaries are preserved.
- [ ] Relevant existing and newly created environments receive the correction.
- [ ] Bootstrap inputs are authenticated and effective trust sources are accounted for.
- [ ] Applicable incident chains are rejected and required legitimate connections succeed.
- [ ] Existing controls, user data, credentials, keys and logs remain usable.
- [ ] Database identity and migration compatibility are established before activation.
- [ ] Final artifacts and actual running processes match their evidence.
- [ ] Secure fallback preserves the edition, correction and current compatible data.
- [ ] Local evidence distinguishes build success from deployment success.
- [ ] Gaps and inaccessible targets remain explicit.

PASS applies only to the recorded target, revision, artifact, configuration and checks actually completed. FAIL takes precedence when a known required condition fails; otherwise required missing evidence prevents PASS.

The handoff must include changed files and reasons, exact authenticated inputs, per-target results, resolved deployment steps, recovery instructions and remaining owners/actions.

## 18. Direct instruction to the coding agent

Implement this paper as a focused Shogun Yellow Label security maintenance release.

Inspect the actual repository, installed edition, launcher, environments and updater. Preserve user changes and local data. Confirm that the code and database belong to a compatible Yellow Label lineage before activating any artifact.

Recheck the primary advisories, authenticate bootstrap tools, correct all effective trust sources and rebuild the actual Yellow Label deliverables. Treat Windows native validation, Python clients, package tooling and updater downloads as distinct paths until evidence shows they share the same corrected configuration.

Keep existing ToolGate controls, permissions and approved local functionality. Preserve credentials, keys, conversations, memory, skills, tasks and existing logs. Add no dependency on Gensui, Nexus, enterprise publication or White Label administration.

Verify affected-chain rejection, legitimate behavior, fresh installation and state-preserving update. Use the actual runtime and final artifact. Mark missing access or evidence INCONCLUSIVE.

Activate the exact tested Yellow Label revision/artifact through existing authority. Provide a secure fallback compatible with current data and a clear local completion record.

Do not stop at changing a requirements file, updating global Python or obtaining a successful browser test. Deliver the correction through the actual installation and document precisely what was and was not verified.

---

## 19. Repository review addendum — 23 October 2026

Version 1.1 incorporates the findings in `Shogun_Yellow_Label_Security_Update_Review_2026-10-23.md`. This addendum records pre-remediation observations, not a deployment result.

### 19.1 Confirmed initial state

The inspected checkout is the public Yellow Label source on `main`, HEAD `007ace3e39bd56eb2a4872bc618e1b80692b4a54`, with existing tracked/untracked user work. `shogun/edition.py` fixes the Yellow Label capability boundary. The observed Windows environment is `.venv/Scripts/python.exe`: Python 3.14.0, pip 25.2, pip-vendored certifi 2025.07.14, application certifi 2026.2.25, and httpx 0.28.1. Host Node is 24.16.0; Playwright 1.60.0 bundles a separate Node 24.15.0. All four inspected CA sets contain emSign ECC Root CA - G3. Its presence and version measurements require remediation but do not replace incident-chain behavioral tests.

`pyproject.toml` has no explicit corrected certifi floor. `install.bat`, `install.sh`, Docker Python stages and CI installation steps need an authenticated pip bootstrap before ordinary package network access. Node/npm is used by both desktop installers, the updater and the frontend Docker builder. Existing Node engine constraints admit affected releases and unsupported Node 23.

### 19.2 Required implementation

1. Add a corrected application certifi floor and maintainable shared checks/bootstrap for the selected interpreter; preserve newer compatible corrected tooling. Record exact security inputs and independently verified hashes. Keep pip as installation tooling rather than adding it as a business dependency.
2. Enforce supported corrected Node 22/24 releases before npm network activity in installers, updater and applicable build paths. Update package engine declarations/lock metadata without unrelated package churn.
3. Inspect and correct Playwright's actual Node driver separately. Use a supported corrected package or a supported tested runtime override; retain browser state and verify Mado/Ronin browser workflows.
4. Resolve the updater source to an immutable commit and fail before downloading a moving branch when resolution is unavailable. Validate required manifests and Yellow Label identity before installation. Reject concurrent application updates.
5. Prepare dependencies and frontend before copying application files. A failed bootstrap, package install, trust check or build must return failure and prevent application-file promotion. Retain recoverable code on copy failures and preserve every existing protected state directory. No schema or edition conversion is authorized by this update.
6. Keep final activation separate from preparation where the existing in-process updater cannot safely validate a replacement runtime. Use the narrow documented operator route rather than claiming transactional rollback of an already-mutated environment. Record partial dependency changes accurately and never return security-update success after a dependency failure.
7. Extend the existing security check entry point with focused regression tests for version boundaries, bootstrap integrity, updater source pinning, failure handling, cleanup, protected-state preservation and positive/negative TLS behavior. Use real incident fixtures as data and classify network/expiry/hostname failures accurately.

### 19.3 Separate PHP runtime incident

This paper remediates eMudhra certificate trust. CVE-2026-109618 and CVE-2026-109619 are separate critical PHP runtime defects; CA updates cannot correct them. Supported patched branches start at PHP 8.2.35, 8.3.36, 8.4.27 and 8.5.12, or an evidenced distributor correction. [S25], [S26]

No tracked PHP source or Composer manifest was found in this checkout, and PHP was not on the review shell's PATH. That evidence does not establish absence from other machines, containers or external services. Record those targets separately when present; do not introduce PHP into Shogun to remediate an absent component.

### 19.4 Preservation and evidence

Preserve existing dirty-tree work, data, credentials, configuration, permissions, logs, browser profiles and pending tasks. Do not run the live updater or application migrations as a test. Use isolated synthetic installations for destructive-path regressions and consistent snapshots where a real state change is necessary. Record dependency changes, test results, artifact identities, deployment status and unresolved platform coverage after implementation. The initial package version floors fail; incident-chain rejection, live process identity and other installations remain unverified until exercised.

---

## 20. Implementation and verification record — version 1.5

The maintenance release is **1.47.119, build 270**, prepared in an isolated checkout on remote main `ede4b879f8acff9aeff97ff141c353c888adb06f`. That parent already contains the existing workbook releases through 1.47.118. Unrelated local integration work and persistent application state are excluded from the security commit and preserved in the original workspace.

Implemented changes:

- An explicit corrected certifi dependency floor and independently hash-authenticated pip/certifi bootstrap before ordinary downloads.
- Corrected Node 22/24 floors in all desktop installers and package engine metadata; application-owned authenticated Node 24.22.1 for Windows and WSL, with no global runtime replacement.
- Explicit corrected Node selection for Mado/Playwright, npm, launchers, updater, CI and containers. Existing Playwright/browser packages and saved profiles are retained.
- Read-only checks for affected root/intermediate trust anchors in Python/custom PEM sources and effective Linux system trust.
- Immutable updater downloads, administrator authorization, Yellow Label validation, protected-state exclusions, dependency/frontend preparation before code promotion, recoverable application-file copies and safe failure responses.
- Worker-owned installation locks and temporary source trees that survive HTTP cancellation; shared in-app/repair preparation; public offline fixtures and opt-in credential-free live verification.
- Vitest 4.1.12 and matching lockfile updates for the code-injection and Windows traversal advisories found by the dependency gate. [S28], [S29]
- Native CA updates before CI's Python downloads. Container builds preserve strict TLS verification and select corrected Node explicitly.
- Trust enforcement on direct CLI and ASGI startup before environment changes, pending restores or database migrations; a shell-launcher bypass does not bypass the correction.

The isolated release passed the complete backend security gate: **664 Python tests passed, four platform-specific skips**, plus lint, clean imports, guide synchronization and telemetry privacy validation. Native Linux shell/security/updater regressions separately passed **85 tests without skips**. The final frontend passed locked installation, TypeScript/Vite build, security lint, **14 security tests**, bundle-size validation and the dependency gate with no moderate/high/critical findings. The audit gate's own **15 regression tests** passed.

Windows and WSL each recorded **45 PASS / 0 FAIL / 0 INCONCLUSIVE** across HTTPX, pip's actual combined trust context and the selected Node runtime, covering all 14 affected endpoints and a legitimate control. The Windows fresh-venv bootstrap and actual headless Playwright/Chromium smoke test also passed. Offline chain tests retain fixed verification times and a positive control.

The authorized interrupted-package repair completed successfully. WSL now has Ubuntu's corrected `ca-certificates` **20260816ubuntu0.24.04.1**, pip 26.2.2, certifi 2026.10.19 and application-owned Node 24.22.1. Its prerequisite gate passes and all 14 previously failing pip incident checks now reject the affected chains. [S27]

A local server-container build filled the Windows host disk and WSL encountered filesystem I/O errors. After disposable task-owned build files were cleared, the operator explicitly approved restarting Ubuntu WSL. Its filesystem and Docker volumes were retained. The existing Qdrant mount and collection remained readable, the package database audit was clean, and the restarted environment again passed all 45 live TLS probes and its native regression suite.

Independent image scans found separate vulnerabilities bundled inside package-manager tooling. The final runtime images exclude pip, its ensurepip seed and npm after dependency/browser/frontend preparation; corrected Node, Playwright/Chromium, the UI and application libraries remain. No vendored source patch or scanner exception was introduced. Desktop installation/update workflows retain corrected pip and npm. A runtime-only read-only trust gate checks certifi and native/custom trust without requiring installer tools; it cannot skip installer bootstrap. Official containers are updated through image replacement with existing data volumes, which the in-app endpoint reports before any package operation.

Both native macOS jobs passed on the initial security commit, with the macOS 14 Safari driver succeeding on a runner retry. The final source is subject to the same protected-main gates. [PR #85](https://github.com/AlphaHorizon-AI/Shogun/pull/85) records exact commit identities and executed CodeQL, backend, frontend, image-scan, container-runtime and native macOS results.

No existing database, credentials, approval state, saved browser profile or persistent volume was replaced or removed. No live application migration, database restore, key/account reset or application restart was used as a test. Code-recovery backups are not presented as independently verified secure fallbacks. Production application activation and other installations require their own recorded results; native-platform and disposable container execution are recorded by the required CI jobs.

The detailed implementation report is `docs/security/emudhra-implementation-2026-10-23.md`; the recovery runbook is `docs/security/emudhra-maintenance.md`; retained local evidence is under `tmp/emudhra-maintenance/`. The final Git commit identifies the release source; old uncommitted candidate archives must not be published as that commit.

---

## 21. Live activation and preservation follow-up — version 1.6

The authorized desktop activation reports running and installed **1.47.119, build 270**, with no pending activation. The authenticated updater restart replaced the live process successfully. Testing used localhost port 8001 because another application occupies the default port; existing credentials and `.env` were retained.

Live smoke testing found and fixed hardcoded launcher browser addresses, a missing enum value for the existing SkillOpt schedule preset, and destructive provider cleanup during local-model discovery. Discovery now preserves saved providers when a daemon reports a different inventory. The six affected provider/catalog rows were recovered from the consistent pre-start backup without overwriting other rows.

Final verification passed: 688 backend tests with four platform skips, frontend build/bundle validation, 16 rendered Yellow Label pages without JavaScript or API server errors, and 27 authenticated feature API reads. Updater checks succeeded; unauthorized privileged calls were rejected; dirty-checkout Apply protection prevented promotion; restricted enterprise endpoints remained blocked. The private preservation comparison confirmed all original table/record identities and files, unchanged schema and credentials, preserved schedule definitions, and healthy existing Qdrant storage. Normal scheduling, inferred-capability, audit and consented-telemetry bookkeeping evolved as documented.

The [activation report](https://github.com/AlphaHorizon-AI/Shogun/blob/main/docs/security/yellow-label-activation-2026-10-23.md) records executed checks and limits. External business actions and live code promotion over local edits were not performed. Backups and private fingerprints remain outside committed release artifacts.

## Project references

### Yellow Label design reference

**[P1] Shogun Yellow Label SkillOpt Lab Build Paper v1.0, 11 September 2026.**

File: `Shogun_Yellow_Label_SkillOpt_Lab_Build_Paper_v1.0.md`.

Used for the local-versus-enterprise capability boundary and shared-core intent. Its proposed features are not treated as confirmed implementation.

### User context

**[P2] User's established Yellow Label product and deployment decisions, retrieved for this request.**

Used for edition exclusions, standalone operation, historical retained-module profiles and Windows installation relevance. Earlier upgrade troubleshooting is a reported context item, not a current diagnosis.

### General remediation reference

**[P3] Shogun Security Update Build Paper, 22 October 2026.**

File: `Shogun_Security_Update_Build_Paper_eMudhra_2026-10-22.md`.

Used as the earlier implementation framework. This paper provides a separate Yellow Label scope and preserves the earlier paper.

## Primary sources

Current incident guidance was rechecked on 23 October 2026. Supporting product documentation was consulted on 22–23 October. Revisit the current advisories before implementation.

External incident facts, release floors and documented product behavior come from these sources. The Yellow Label workflow, preservation rules, acceptance criteria and work packages are this paper's implementation design.

| Reference | Source and use |
| --- | --- |
| [S1] | Python incident guidance and recommended ecosystem corrections. |
| [S2] | Mozilla incident record and independently verified key compromise. |
| [S3] | certifi maintainer advisory and initial correction. |
| [S4] | Mozilla security notice and interception prerequisite. |
| [S5] | Incident disclosure, platform status and verification resources. |
| [S6] | pip HTTPS verification and combined certificate sources. |
| [S7] | Debian correction for direct and alternate trust paths. |
| [S8] | pip changelog and updated vendored dependencies. |
| [S9] | uv maintainer advisory and corrected baseline. |
| [S10] | Python branch releases and authenticated pip bootstrap. |
| [S11] | pip 26.2.2 metadata and interpreter requirement. |
| [S12] | certifi 2026.10.19 metadata and interpreter requirement. |
| [S13] | uv native and custom certificate configuration. |
| [S14] | pip complete dependency hashing. |
| [S15] | Docker build inputs, image pinning and cache behavior. |
| [S16] | Incident root identities and fingerprints. |
| [S17] | Python virtual-environment isolation, layout and portability. |
| [S18] | Microsoft trusted and untrusted CTL management. |
| [S19] | Python SSL implementation and certificate loading. |
| [S20] | truststore native backends and integration boundaries. |
| [S21] | SQLite consistent backup API. |
| [S22] | Alembic migration branches and multiple-head semantics. |
| [S23] | SQLite WAL state and associated files. |

[P1]: #yellow-label-design-reference
[P2]: #user-context
[P3]: #general-remediation-reference
[S1]: https://discuss.python.org/t/information-for-python-users-regarding-emudhra-emsign-ca-certificate-security-incident/109576
[S2]: https://bugzilla.mozilla.org/show_bug.cgi?id=2083449
[S3]: https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2
[S4]: https://blog.mozilla.org/security/2026/10/20/protecting-firefox-users-following-the-compromise-of-emudhra-intermediate-certificates/
[S5]: https://emudhra.we-have-a-problem.com/
[S6]: https://pip.pypa.io/en/stable/topics/https-certificates/
[S7]: https://bugs.debian.org/1151413
[S8]: https://pip.pypa.io/en/stable/news/
[S9]: https://github.com/astral-sh/uv/security/advisories/GHSA-hq85-5cpj-mr62
[S10]: https://blog.python.org/2026/10/python-3151-3149-31317/
[S11]: https://pypi.org/project/pip/26.2.2/
[S12]: https://pypi.org/project/certifi/2026.10.19/
[S13]: https://docs.astral.sh/uv/concepts/authentication/certificates/
[S14]: https://pip.pypa.io/en/stable/topics/secure-installs/
[S15]: https://docs.docker.com/build/building/best-practices/
[S16]: https://emudhra.we-have-a-problem.com/roots.json
[S17]: https://docs.python.org/3/library/venv.html
[S18]: https://learn.microsoft.com/en-us/windows-server/identity/ad-cs/certificate-trust
[S19]: https://docs.python.org/3/library/ssl.html
[S20]: https://truststore.readthedocs.io/en/latest/
[S21]: https://www.sqlite.org/backup.html
[S22]: https://alembic.sqlalchemy.org/en/latest/branches.html
[S23]: https://www.sqlite.org/wal.html



[S24]: https://nodejs.org/en/blog/vulnerability/october-2026-security-releases
[S25]: https://github.com/php/php-src/security/advisories/GHSA-w8hw-w9fx-j79w
[S26]: https://github.com/php/php-src/security/advisories/GHSA-6wmf-4rv5-p3rp

[S27]: https://ubuntu.com/blog/emudhra-ca-compromise-fixes-available

[S28]: https://github.com/vitest-dev/vitest/security/advisories/GHSA-qxg6-89mg-rqv8
[S29]: https://github.com/vitest-dev/vitest/security/advisories/GHSA-xp26-3454-mjgp
