# Security policy

Alpha Horizon encourages users and security researchers to report suspected
vulnerabilities, compromises, unsafe defaults, exposed credentials, unexpected
security-relevant behaviour, and privacy or security incidents as soon as
possible.

## Security contact and reporting routes

Use the route that matches the sensitivity of the report:

- **Confidential vulnerability report:** use [GitHub Private Vulnerability
  Reporting](https://github.com/AlphaHorizon-AI/Shogun/security/advisories/new).
- **Human-routed security contact:** email
  [contact@alphahorizon.io](mailto:contact@alphahorizon.io?subject=Shogun%20Security%20Report)
  with the subject `Shogun Security Report`. Email may not be end-to-end
  encrypted, so use it for initial contact and agree a secure exchange method
  before sending secrets or exploit details.
- **Public, non-sensitive report:** [open a GitHub
  issue](https://github.com/AlphaHorizon-AI/Shogun/issues/new) only when the
  report is safe to disclose publicly.

Do not put exploit-enabling details, credentials, personal or customer data,
prompt content, production telemetry tokens, installation identifiers, or
unredacted logs in a public issue. If in doubt, use a confidential route.

The routes above are the single product-security contact for Shogun AFM and are
monitored for vulnerability intake and coordinated disclosure. The public
website for the manufacturer is [alphahorizon.io](https://www.alphahorizon.io/).

## Security-report privacy

Alpha Horizon uses security-report data to receive and investigate the report,
communicate with the reporter, protect Shogun users, coordinate remediation and
disclosure, and meet applicable legal obligations. Please provide only the
personal data needed for those purposes.

Access is limited to authorized security, product, legal, and communications
personnel and service providers needed to operate the reporting channel. Data
may be shared on a need-to-know basis with an affected component maintainer,
coordinator CSIRT, ENISA, competent authority, or professional adviser when
necessary for remediation or compliance. Public disclosure does not identify a
reporter without permission unless disclosure is legally required.

Reporter contact data is removed or pseudonymized when it is no longer needed
for follow-up, legal claims, or mandatory record-keeping. Incident evidence and
regulatory records are protected under the incident-retention schedule and
reviewed periodically for continued necessity. Questions or requests about a
security report can be sent to [contact@alphahorizon.io](mailto:contact@alphahorizon.io)
with the report identifier. The legal Alpha Horizon entity, postal address,
applicable legal basis, retention periods, and data-subject rights must also be
stated in the distribution-specific privacy notice before an EU production
release.

## Official releases, vulnerability handling, and support boundaries

An official release is a version and build published by Alpha Horizon through
its official release channel and identified in `version.json`. Alpha Horizon
handles security vulnerabilities affecting official, unmodified Shogun
releases in accordance with applicable legal obligations and any support or
vulnerability-handling period required under applicable law.

Alpha Horizon may publish corrective or mitigating measures through official
[Releases](https://github.com/AlphaHorizon-AI/Shogun/releases), published
[security advisories](https://github.com/AlphaHorizon-AI/Shogun/security/advisories),
or the Shogun **Updates** channel where Alpha Horizon determines this appropriate
or where required by applicable law. This policy does not promise that every
reported issue will result in a patch. Where an applicable legal obligation
requires a security update to be provided without charge, that obligation is
preserved. Installation requires an operator action, and remediation may require
installation of a later official build where permitted by applicable law.

Shogun is provided without a standard maintenance agreement, helpdesk,
service-level agreement, or commitment to ongoing feature development,
compatibility maintenance, integration maintenance, or LLM/provider
compatibility work. Security vulnerability handling for official releases is
separate from general customer support and is performed where Alpha Horizon
elects to provide it or where required by applicable law. Broader support exists
only under a separate written agreement.

Customer or third-party modifications are not validated, certified, or
maintained by Alpha Horizon, and Alpha Horizon does not undertake to patch or
support defects introduced by those modifications. Reports from modified
installations remain welcome so Alpha Horizon can determine whether an issue is
also attributable to an official release. Responsibility for issues attributable
to official Alpha Horizon releases remains subject to applicable law. Nothing in
this policy limits rights or responsibilities that cannot legally be excluded.

No voluntary fixed retention period is created by this policy. Security updates,
advisories, technical documentation, user instructions, and incident records are
retained or made available for the periods required by applicable statutory
documentation, disclosure, update-availability, and record-retention obligations.
In particular, where Article 13 of the EU Cyber Resilience Act applies to a
release, each qualifying security update made available during the statutory
support period remains available for at least 10 years after issuance or for
the remainder of that support period, whichever is longer, as required by
Article 13(9). Technical documentation, the EU declaration of conformity, and
user instructions remain available for at least 10 years after the product is
placed on the market or for the applicable support period, whichever is longer,
as required by Article 13(13) and 13(18).

## What to include

Please provide as much of the following as can be shared safely:

- the Shogun version and build shown on the Updates page or in `version.json`;
- operating system and desktop or server deployment type;
- affected component and a concise description of the security or privacy
  impact;
- UTC timestamps, relevant trace or AgentFlow run IDs, and safe reproduction
  steps;
- sanitized logs, expected versus observed behaviour, and mitigations already
  attempted;
- whether exploitation appears active and a secure way to contact you.

Remove secrets, personal data, customer data, prompts, proprietary content, and
unrelated system information before submitting evidence.

## Immediate containment

If active compromise is suspected, stop the affected workflow, activate
Harakiri where appropriate, and isolate the affected instance from untrusted
networks. Preserve audit records and timestamps rather than deleting evidence.
From a trusted device, revoke or rotate credentials that may have been exposed.
Containment does not replace reporting the incident.

## Coordinated vulnerability disclosure

Alpha Horizon aims to acknowledge and triage security reports promptly. No
specific customer-support response time is promised by this policy.

For reports affecting official releases, Alpha Horizon's coordinated process
may include the following steps as appropriate:

1. acknowledge and triage the report;
2. validate affected versions, assess severity and exploitation evidence, and
   identify third-party components where relevant;
3. maintain contact with the reporter when clarification or coordinated testing
   is useful;
4. develop corrective or mitigating measures and communicate urgent
   containment guidance when appropriate;
5. publish an advisory identifying affected versions, impact, severity, and
   remediation after users have had a reasonable opportunity to apply an
   available fix; and
6. credit reporters who request attribution and whose disclosure was
   coordinated, unless legal or safety constraints prevent it.

Please coordinate public disclosure of an unpatched vulnerability with Alpha
Horizon. Regulatory reporting or an immediate risk to users may require a
different disclosure timeline.

## Security verification and AI-assisted red teaming

Shogun preserves automated security regression tests, dependency and code
scanning, and conventional review controls. Alpha Horizon may also use
AI-assisted adversarial review or red-team exercises to identify hypotheses and
test cases for human investigation. Useful findings and the regression tests
created from accepted findings are retained with the relevant development or
release records where practical.

AI-assisted red teaming supplements rather than replaces threat modelling,
secure code review, dependency management, reproducible testing, penetration
testing where appropriate, human assessment, and incident handling. Neither an
AI-assisted review nor a passing automated test guarantees security, record
completeness, regulatory conformity, or suitability for a particular
deployment.

## CRA incident escalation

Opening a GitHub report notifies Alpha Horizon; it does not itself complete a
statutory notification. From 11 September 2026, when Alpha Horizon has
applicable manufacturer or other economic-operator duties under Regulation (EU)
2024/2847 (the Cyber Resilience Act), an actively exploited vulnerability or a
severe incident affecting the security of Shogun is escalated through the ENISA
Single Reporting Platform:

- early warning without undue delay and no later than 24 hours after awareness;
- substantive notification and initial assessment no later than 72 hours after
  awareness;
- final vulnerability report no later than 14 days after a corrective or
  mitigating measure is available; or
- final severe-incident report within one month after the 72-hour notification.

The incident lead records the time at which Alpha Horizon became aware, the
classification decision, affected releases and EU markets, evidence of active
exploitation or severe impact, user-notification decisions, corrective
measures, and every regulatory submission. See the internal [CRA incident
response procedure](docs/security/cra-incident-response.md).

Official references:

- [Regulation (EU) 2024/2847](https://eur-lex.europa.eu/eli/reg/2024/2847/2024-11-20/eng)
- [European Commission CRA reporting guidance](https://digital-strategy.ec.europa.eu/en/policies/cra-reporting)
- [ENISA Single Reporting Platform](https://www.enisa.europa.eu/topics/product-security/single-reporting-platform-srp)

## Installation telemetry

Installation telemetry is a distinct, default-off privacy boundary. Its exact
schema and controls are documented in [docs/telemetry.md](docs/telemetry.md).
Reports about unexpected traffic, consent bypass, schema expansion, deletion,
token exposure, dashboard authorization, or retained IP addresses are treated
as security and privacy incidents.

This policy supports coordinated handling and CRA readiness. It is not legal
advice and does not by itself establish conformity. Product classification,
cybersecurity risk assessment, technical documentation, conformity assessment,
EU declaration of conformity, manufacturer postal details, and national-law
interactions require owner and legal validation for each distribution model.
