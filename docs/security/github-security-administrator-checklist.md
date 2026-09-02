# GitHub Security Administrator Checklist

This checklist separates repository-controlled safeguards from GitHub settings
that require a repository or organisation administrator. It is an operational
record, not a claim that every available GitHub control is enabled.

## Verified on 21 August 2026

The following read-only checks were performed against
`AlphaHorizon-AI/Shogun` using GitHub's API. No advisory was created and no
repository setting was changed.

| Control | Verification result |
| --- | --- |
| Private vulnerability reporting | **Enabled.** The repository exposes GitHub's private vulnerability-reporting route. Keep it enabled. |
| Dependency graph | **Available.** GitHub returned a machine-readable SPDX 2.3 dependency-graph SBOM. |
| Dependabot alerts | **Available.** The alert API was accessible and returned no open alerts at verification time. Alert counts can change. |
| Dependabot security updates / automated fixes | **Enabled.** Both repository security-update metadata and the automated-security-fixes API reported enabled. |
| Code scanning | **Active.** The CodeQL workflow is active. Four open alerts existed on verified commit `0774ce5998400963541a19b78e81e97dfea0ad4e`; remediation is included in the subsequent hardening change and must be confirmed by the next CodeQL run. |
| Secret scanning | **Disabled.** Administrator action is required. |
| Secret-scanning push protection | **Disabled.** Administrator action is required. |

The repository also contains code-controlled CodeQL, Trivy, dependency-audit,
container, telemetry-privacy, and security-regression workflows. These controls
supplement one another; none guarantees that the software is free of
vulnerabilities.

The four alerts in that snapshot were: high-severity polynomial regular
expressions in `shogun/services/enterprise_transformations.py` and
`shogun/mapping/engine.py`, high-severity clear-text logging of a validation
error in `shogun/engine/flow_engine.py`, and medium-severity external exception
information exposure in `shogun/api/agents.py`. The follow-up changes replace
the regex parsing with bounded string scanning and remove raw exception/provider
response details from logs, audit events, and client errors. GitHub—not this
document—is authoritative for whether a later analysis has closed each alert.

## Administrator actions

In **Repository settings → Code security and analysis** (wording may change in
GitHub), an authorised administrator should:

1. Enable secret scanning for the repository.
2. Enable push protection for detected secrets.
3. Decide whether non-provider patterns and validity checks are appropriate for
   the organisation's false-positive and data-handling policies.
4. Confirm dependency graph, Dependabot alerts, Dependabot security updates,
   and CodeQL/default setup remain enabled after repository or organisation
   policy changes.
5. Triage open code-scanning, dependency, and secret-scanning alerts according
   to the project's security process. Do not copy exploit details or secrets
   into public issues.
6. Keep **Security → Report a vulnerability** available. Test navigation only;
   do not create a dummy security advisory.
7. Confirm branch/ruleset protections require the security workflows that the
   repository owner considers release gates.
8. Re-run this verification after ownership, visibility, plan, or organisation
   policy changes because feature availability can change.

## Release evidence

`.github/workflows/release-evidence.yml` generates two non-confidential,
machine-readable artifacts from the exact checked-out release source:

- `release-metadata.json` records semantic version, build, release date, and
  the full Git commit SHA.
- `shogun-direct-dependencies.spdx.json` is an SPDX 2.3 SBOM covering direct
  runtime Python dependencies for Shogun and the telemetry service
  (including non-development optional groups), plus locked production
  dependencies for The Tenshu.
  Python constraints are preserved as declaration metadata and are not
  misrepresented as resolved installed versions.

For a published GitHub release the workflow attaches both files to that
release. A manually dispatched run retains them as a workflow artifact. Release
authors may add `security_changes` and `breaking_changes` string arrays to
`version.json`; those fields are carried into release evidence and the update
UI without requiring exploit details to be disclosed prematurely.

The GitHub dependency graph's broader SPDX SBOM remains useful as supplemental
evidence. Its inventory may differ from the release-specific direct-dependency
SBOM because GitHub refreshes the graph independently.
