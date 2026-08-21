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

## Official releases and security-vulnerability handling period

An official release is a version and build published by Alpha Horizon through
its official release channel and identified in `version.json`.

| Release family | Security vulnerability handling | Published end date |
| --- | --- | --- |
| Official, unmodified Shogun AFM 1.x | Latest stable official 1.x build | 31 August 2031 |

This security-vulnerability handling period covers vulnerability intake,
assessment, corrective or mitigating security measures, and security updates
for defects attributable to official, unmodified Shogun releases. It is not
general technical support and does not include a helpdesk, feature development,
compatibility maintenance, integration maintenance, LLM or provider
compatibility updates, a service-level agreement, or support for defects
introduced exclusively by customer-modified builds. Broader support exists only
under a separate written agreement.

Corrective or mitigating measures are published through official
[Releases](https://github.com/AlphaHorizon-AI/Shogun/releases), published
[security advisories](https://github.com/AlphaHorizon-AI/Shogun/security/advisories),
and the Shogun **Updates** channel when Alpha Horizon determines them appropriate
or legally required. Security updates covered by an applicable legal obligation
are provided without charge. Shogun checks for updates automatically, but
installation requires an operator action. Where permitted by applicable law,
remediation may require installation of the latest stable official 1.x build;
any latest-version correction path remains subject to the conditions imposed by
applicable law.

31 August 2031 is the published end date for the currently identified official,
unmodified Shogun AFM 1.x product line. It does not shorten a longer period
required by law or by the documented expected-use assessment. A later official
release requiring a separate product or security-period assessment will receive
its own published end date. Reports from modified installations remain welcome
so Alpha Horizon can determine whether an official release is also affected.
Nothing in this policy limits rights or responsibilities that cannot legally be
excluded.

Issued security updates and their accompanying advisories will remain
available for at least ten years after issuance or for the remainder of the
applicable security-vulnerability handling period, whichever is longer.

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

Alpha Horizon will:

1. acknowledge and triage the report, with a target human acknowledgement
   within three business days;
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
