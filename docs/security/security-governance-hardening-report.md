# Security Governance Hardening — Implementation Report

Date: 21 August 2026

This report records engineering and documentation work that supports Shogun's
security-governance and regulatory-readiness processes. It is not legal advice,
a conformity assessment, or a claim that Shogun or a particular deployment is
CRA-, AI Act-, or GDPR-compliant.

## 1. Files changed

The principal changed surfaces are:

- Repository policy and product documentation: `SECURITY.md`, `README.md`,
  `LICENSE.md` references (the licence text itself was not changed), the Tenshu
  and Gensui Guides, privacy/deployment/reference documentation, and the CRA
  incident-response procedure.
- Installation and onboarding: desktop and server installers, Gensui installers,
  Setup Wizard, setup API/schema, first-run authorization, environment bootstrap,
  and installer provenance tests.
- Persistent UI access: Sidebar, Guide navigation, About/System Information,
  Privacy & Telemetry, Ronin, Logs/Fleet Audit, and Gensui Identity surfaces.
- Release evidence: version/build metadata, updater provenance, backup manifests,
  Docker VCS metadata, release-evidence workflow, SPDX generation, and release tests.
- Runtime security: Ronin/PostureGuard/approval enforcement, HARAKIRI wording and
  state transitions, College telemetry consent, provider-error redaction, bounded
  parsing, scoped Team memory/chat retrieval, and audit terminology.
- GitHub/CI: issue forms, CodeQL and security-hardening workflows, immutable action
  references, repository security checklist, and expanded security regression gates.
- Localized UI catalogs and generated frontend distributions were regenerated to
  match the source changes.

## 2. New files created

- `.github/ISSUE_TEMPLATE/bug-report.yml`
- `.github/workflows/release-evidence.yml`
- `docs/security/github-security-administrator-checklist.md`
- `frontend/src/lib/guideNavigation.ts` and its test
- `frontend/src/lib/infrastructureAuth.test.ts`
- `frontend/src/pages/About.tsx`
- `scripts/generate_release_evidence.py`
- `scripts/write_release_metadata_evidence.py`
- `shogun/environment_bootstrap.py`
- `shogun/services/release_metadata.py`
- `shogun/setup_link.py`
- Security-focused regression files for desktop/server bootstrap, Gensui identity
  and installers, release evidence/metadata, Ronin gates, governance language,
  parsing, workflow pinning, setup acknowledgement, and updater provenance.

Generated hashed frontend assets are build artifacts and are not individually
listed here.

## 3. Installer and UI components changed

- Setup is now ten steps and includes a mandatory **Security & Incident
  Reporting** step.
- The setup API rejects missing or false acknowledgement values and stores the
  server-generated acknowledgement record locally with timestamp, role,
  version, build, and release identifier.
- Incident Reporting and About remain available from persistent navigation.
- Desktop and server bootstrap URLs carry the infrastructure credential only in
  a loopback URL fragment; the frontend removes it before React/API activity.
- Desktop environment files are created atomically and restricted to the local
  administrator and trusted OS principals. Server and Gensui installers use
  private temporary workspaces, immutable source revisions, supported runtime
  ranges, cleanup, and fail-closed dependency/build handling.
- About displays release identity and whether tracked source appears locally
  modified, without exposing an instance identifier.

## 4. Exact acknowledgement wording

> I acknowledge that I have been provided with the Shogun security and incident
> reporting information and know where to report suspected security vulnerabilities.

This is an acknowledgement of information, not a liability waiver. It remains
local and is forbidden by the installation and College telemetry schemas.

## 5. Existing security functionality preserved

- Public non-sensitive issue reporting and confidential GitHub private
  vulnerability reporting are separate.
- No placeholder Security Advisory was created.
- HARAKIRI, ToolGate, Torii, PostureGuard, audit/trace records, AI-assisted red-team
  tests, server-mode control-plane authorization, and private vulnerability routes
  remain available.
- Runtime documentation was narrowed where implementation is bounded or
  best-effort; this does not remove the underlying controls.
- Team connector memory and Telegram conversation history are now forced through
  exact principal/conversation/topic authorization even if global retrieval is
  configured as legacy or shadow.
- OpenClaw College telemetry now defaults off, requires an explicit current-notice
  opt-in, fails closed for legacy implicit opt-ins, and rechecks consent immediately
  before network delivery.

## 6. GitHub settings requiring owner verification or action

At the time of review, private vulnerability reporting, the dependency graph,
Dependabot security updates, and CodeQL were available. No dummy advisory was
created. Repository owners should continue to verify those settings and reporter
notifications because GitHub settings can change independently of this codebase.

Manual action remains necessary for:

- enabling secret scanning and push protection if the repository plan/settings
  permit them;
- confirming that repository administrators/security managers receive private
  vulnerability report notifications;
- rerunning CodeQL after these local Phase 2 changes are published and closing or
  documenting any remaining alerts; and
- reviewing the administrator checklist after repository or plan changes.

## 7. Licence wording requiring legal review

`LICENSE.md` was not changed. The documentation now says "free to use" only for
purposes permitted by the Shogun AFM Free Use License, describes Shogun as
source-available rather than open source, and preserves redistribution,
rebranding, hosted-service, production, at-scale, customer-facing, and commercial
restrictions. Counsel should confirm that the product copy, internal-modification
description, disclaimer, and any separately agreed commercial/support terms remain
consistent with the licence and applicable mandatory law.

## 8. CRA wording requiring legal review

The material distinguishes ordinary defects, suspected vulnerabilities, actively
exploited vulnerabilities, and severe security incidents. It documents the
manufacturer escalation process and the ENISA Single Reporting Platform without
making every user report automatically regulatory-reportable.

Qualified review is still required for manufacturer/economic-operator identity,
postal details, product classification, expected-use/support-period assessment,
conformity assessment, technical documentation, EU Declaration of Conformity/CE
steps, national-law interactions, and the operational 24/72-hour/final-report
process. The reporting procedure must be rehearsed before the applicable date.

## 9. AI Act wording requiring legal review

The documentation states the factual architecture: Shogun is model-agnostic
orchestration software and is not itself an LLM, foundation model, or GPAI model;
the deploying organisation selects local or cloud models. It does not conclude
that Shogun or a deployment falls outside the AI Act. Qualified review is needed
for Alpha Horizon's role and each deployment's role/use-case classification,
connected models, autonomy, tools, transparency, human oversight, and any
high-risk or downstream-provider obligations.

## 10. Official releases versus modified customer installations

Official releases are source and release artifacts published by Alpha Horizon.
Independent customer/third-party changes are described as modified installations,
not Alpha Horizon-validated or certified releases. The modifier must assess the
effects of its changes. The wording preserves responsibility for defects
attributable to official Alpha Horizon code and any duty that cannot legally be
excluded. About separately reports a locally modified tracked checkout when Git
evidence is available.

## 11. Release-specific statutory support periods

The earlier voluntary fixed calendar-date statement was removed. The security policy
now ties vulnerability handling, update availability, documentation retention,
and any published support-period end date to the obligations that apply to the
relevant release. It does not create a general helpdesk, maintenance, feature,
compatibility, integration, model-provider, or service-level commitment.

Before a release is placed on a market where the Cyber Resilience Act applies,
the owner and qualified counsel must determine and document the legally required
support period from the product's expected use and the other Article 13(8)
factors, then publish the required month and year. Article 13's separate update
availability and documentation-retention duties must be applied to that release.

## 12. Remaining compliance and security gaps

- Legal entity/manufacturer postal details and the formal CRA conformity package
  are incomplete.
- AI Act role/use-case classification and GDPR lawful-basis, transfer,
  controller/processor, retention, and DPIA assessments remain deployment- and
  engagement-specific legal work.
- Security/legal text uses canonical English fallback in several locale packs;
  professional reviewed translations are still required for target markets.
- The application audit chain uses an application-level HMAC, selected-field
  coverage, and writable SQLite storage. It is not WORM storage and does not
  independently prove completeness or enforce retention. These limits are now
  disclosed but remain technical assurance work.
- The generated SPDX 2.3 SBOM covers direct declared dependencies; Python
  constraints are not falsely represented as resolved versions. Transitive and
  built-artifact dependency attestations can be expanded later.
- Gensui enterprise identity is configuration staging only. Service-account keys
  are rejected and OIDC/SAML/SPIFFE authentication remains unavailable until a
  complete verifier and endpoint integration exist.
- Secret scanning and push protection remain disabled pending repository-owner
  action, and current CodeQL alerts require a post-publication scan.
- The current Git tree no longer contains the customer-specific private
  transformation profile, but historical public commits still contain the
  earlier blobs. Removing that history requires a separately authorized,
  coordinated history rewrite and credential/content exposure assessment.

## Verification summary

- CI-equivalent focused Python security suite: 269 passed, 1 platform-specific skip.
- Additional Team memory/chat isolation tests: passed.
- Tenshu Setup i18n: 175 keys across 15 locales.
- Tenshu and Gensui production builds: passed.
- Telemetry privacy contract: passed.
- Scoped Ruff security boundary: passed.
- `git diff --check`: no whitespace errors (Windows line-ending warnings only).

Phase 1 documentation hardening was published as Shogun `1.47.83`, build `234`,
commit `0774ce5998400963541a19b78e81e97dfea0ad4e`. This Phase 2 report accompanies
Shogun `1.47.84`, build `235`.
