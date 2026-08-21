# CRA incident-response procedure

This procedure gives Alpha Horizon maintainers a repeatable intake, triage,
remediation, disclosure, and regulatory-escalation workflow for Shogun AFM.
It supports Cyber Resilience Act (CRA) readiness; it is not legal advice and
must be validated against the facts of each event and the applicable role of
Alpha Horizon.

## Public reporting points

- Confidential reports: <https://github.com/AlphaHorizon-AI/Shogun/security/advisories/new>
- Human-routed initial contact: <contact@alphahorizon.io> (subject `Shogun Security Report`).
  Email may not be end-to-end encrypted; agree a secure exchange method before
  sending secrets or exploit details.
- Public, non-sensitive reports: <https://github.com/AlphaHorizon-AI/Shogun/issues/new>
- Disclosure and security policy: [SECURITY.md](../../SECURITY.md)

Never ask a reporter to place exploit-enabling details, credentials, personal
or customer data, prompt content, production telemetry identifiers, or
unredacted logs in a public issue.

## Required ownership

Before an EU production release, Alpha Horizon must assign named people and
backups for these roles and keep their contact details in the restricted
incident register:

| Role | Responsibility |
| --- | --- |
| Incident lead | Owns the timeline, classification, evidence, decisions, and hand-offs |
| Security engineering | Reproduces safely, contains, remediates, tests, and prepares advisories |
| Product owner | Identifies supported releases, components, users, and distribution footprint |
| Legal/compliance | Confirms CRA role, notification threshold, coordinator CSIRT, and submission content |
| User communications | Delivers mitigation, update, and post-incident notices without unsafe disclosure |

The role assignment must include an out-of-hours escalation path because the
CRA early-warning clock is measured in hours, not business days.

## Intake record

Create one restricted incident record immediately. Record facts rather than
conclusions:

- report identifier, intake channel, reporter contact, and receipt time in UTC;
- earliest verified time at which Alpha Horizon became aware of the relevant
  exploitation evidence or incident;
- Shogun version/build, deployment type, operating system, affected component,
  and relevant third-party dependencies;
- affected users, products, data or functions and the EU Member States where
  the affected product was made available;
- trace/run identifiers, sanitized evidence location, indicators of compromise,
  reproduction status, and mitigations already applied;
- confidentiality classification and everyone given access to the evidence;
- current incident lead and time of every decision or regulatory submission.

Preserve original evidence with integrity metadata. Do not place secrets or
personal data into public tickets or general-purpose chat.

Apply the security-report privacy section in `SECURITY.md`: restrict access,
record every disclosure, minimize personal data, and remove or pseudonymize
reporter contact details when no longer needed. Before an EU production
release, legal/compliance must approve the controller identity, legal basis,
retention schedule, processor list, international-transfer safeguards, and
data-subject request process in the applicable privacy notice.

## Initial classification

The incident lead and legal/compliance owner must answer these questions
without delaying urgent containment:

1. **Potential vulnerability:** Is there a weakness that could adversely affect
   Shogun's cybersecurity?
2. **Actively exploited vulnerability:** Is there reliable evidence that a
   malicious actor exploited the vulnerability without the system owner's
   permission?
3. **Incident affecting product security:** Did an event negatively affect, or
   is it capable of negatively affecting, protection of the availability,
   authenticity, integrity, or confidentiality of data or functions?
4. **Severe incident:** Does the impact concern sensitive or important data or
   functions, or did/could it lead to malicious-code introduction or execution?
5. **Third-party origin:** Is the weakness in an integrated component? This
   does not automatically remove Alpha Horizon's reporting or remediation duty.
6. **Other regimes:** Could NIS2, GDPR, contractual, sector-specific, insurance,
   or law-enforcement notification also apply?

If the evidence is incomplete, record the uncertainty and reassess as new facts
arrive. Do not wait for root-cause certainty before starting a deadline that the
law ties to awareness.

## CRA notification clock

The CRA Article 14 reporting obligations apply from **11 September 2026**. When
Alpha Horizon has an applicable manufacturer or other economic-operator duty, use
the ENISA Single Reporting Platform and the appropriate coordinator CSIRT.

| Stage | Maximum time from awareness | Minimum operational action |
| --- | --- | --- |
| Early warning | 24 hours | Identify product, event type, Member States where available, suspected malicious act and cross-border impact when known |
| Substantive notification | 72 hours | Add initial severity/impact assessment, affected versions, exploitation/incident information and mitigations |
| Final — actively exploited vulnerability | 14 days after a corrective or mitigating measure is available | Root cause, corrective measure, deployment status and prevention actions |
| Final — severe incident | One month after the 72-hour notification | Detailed incident, root cause, mitigation/correction and prevention actions |

Regulatory submissions must not be delegated to a public GitHub reporter. A
GitHub issue or private advisory is an intake channel, not the ENISA report.
Record the submitted payload, confirmation, recipients, time, and any later
updates in the restricted incident record.

## Response workflow

1. **Contain safely.** Stop dangerous workflows, use Harakiri when appropriate,
   isolate affected systems, revoke exposed credentials from a trusted device,
   and preserve evidence.
2. **Reproduce and scope.** Use a segregated environment. Identify affected and
   unaffected versions, default configurations, foreseeable misuse, integrated
   components, and the distribution footprint.
3. **Mitigate.** Assess immediate, safe mitigations and publish them where Alpha
   Horizon determines this appropriate or where required by applicable law. Do
   not disclose information that materially increases risk.
4. **Correct and verify.** Where a correction is chosen or legally required,
   develop the smallest safe correction, add regression tests, run security
   review, verify update authenticity and rollback/recovery, and document
   remaining risk.
5. **Coordinate upstream.** Notify an affected component supplier or maintainer
   through its confidential disclosure channel while retaining responsibility
   for the Shogun product response.
6. **Notify users.** Satisfy applicable user-notification duties. Where Alpha
   Horizon otherwise chooses to notify users, describe the issue, impact,
   affected releases, mitigation, available correction, and installation path.
   Coordinate timing with the reporter and authorities.
7. **Publish an advisory.** Where appropriate or legally required, publish
   affected versions, severity, impact, remediation, credit (with permission),
   and links to verified updates once disclosure is safe.
8. **Close and learn.** Confirm deployment status, complete required final
   reports, record lessons and risk-control changes, and track all actions to
   completion.

## Security-update and vulnerability-handling controls

- Alpha Horizon handles security vulnerabilities affecting official, unmodified
  Shogun releases in accordance with applicable legal obligations and any
  support or vulnerability-handling period required under applicable law.
- Shogun has no standard maintenance agreement, helpdesk, service-level
  agreement, or commitment to feature development, compatibility maintenance,
  integration maintenance, or LLM/provider compatibility work. Security
  vulnerability handling is separate from general customer support and is
  performed where Alpha Horizon elects to provide it or where required by law.
  Broader support exists only under a separate written agreement.
- Alpha Horizon may publish corrective or mitigating measures through the
  official repository and Shogun Updates channel where it determines this
  appropriate or where required by applicable law. This procedure does not
  promise a patch for every report. A security update is provided without charge
  where an applicable legal obligation requires that result.
- Where permitted by applicable law, remediation may require the latest stable
  official 1.x build. Any latest-version correction path remains subject to the
  conditions imposed by applicable law.
- Customer or third-party modifications are not validated, certified, or
  maintained by Alpha Horizon. Alpha Horizon does not undertake to patch defects
  introduced by those modifications. Reports remain welcome so Alpha Horizon
  can determine whether official release code is also affected. Responsibility
  for official-release defects and non-excludable rights remains subject to law.
- No voluntary fixed retention period is created by this procedure. Apply the
  statutory documentation, disclosure, update-availability, and record-retention
  periods that govern the relevant release. Where CRA Article 13 applies, retain
  each qualifying security update made available during the statutory support
  period for at least 10 years after issuance or for the remainder of that
  support period, whichever is longer, as required by Article 13(9). Retain
  technical documentation, the EU declaration of conformity, and user
  instructions for at least 10 years after the product is placed on the market
  or for the applicable support period, whichever is longer, as required by
  Article 13(13) and 13(18).
- Release documentation must explain secure update installation, material
  security effects of changes, rollback/recovery, and secure decommissioning
  and user-data removal.

## CRA readiness checks outside an incident

An incident procedure is only one part of CRA readiness. The product owner must
also maintain and validate:

- product classification, intended purpose, security environment, foreseeable
  misuse, cybersecurity risk assessment, and technical documentation;
- a machine-readable software bill of materials and third-party component due
  diligence;
- vulnerability handling, regular tests and reviews, remediation metrics, and
  secure update delivery;
- manufacturer legal/postal and digital contact details, the EU declaration of
  conformity where applicable, conformity assessment, and CE marking;
- where legally required, a release-specific support-period assessment and
  published end date, together with the secure commissioning, operation, update,
  change, integration, and decommissioning instructions required by CRA Annex II;
- named incident roles, coordinator-CSIRT/ENISA access, an EU Login account, and
  a tested 24-hour reporting exercise; and
- preservation of user instructions, technical documentation, issued security
  updates, advisories, and evidence for the applicable retention periods.

## Official sources

- [Regulation (EU) 2024/2847](https://eur-lex.europa.eu/eli/reg/2024/2847/2024-11-20/eng)
- [European Commission CRA reporting obligations](https://digital-strategy.ec.europa.eu/en/policies/cra-reporting)
- [ENISA Single Reporting Platform](https://www.enisa.europa.eu/topics/product-security/single-reporting-platform-srp)
- [ENISA SRP frequently asked questions](https://www.enisa.europa.eu/topics/product-security/single-reporting-platform-srp/frequently-asked-questions)
