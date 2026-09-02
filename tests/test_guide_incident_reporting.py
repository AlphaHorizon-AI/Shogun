from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from scripts.sync_guide_translations import extract_fragments

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "frontend" / "src" / "pages" / "Guide.tsx"
SECURITY_POLICY = ROOT / "SECURITY.md"
CRA_PROCEDURE = ROOT / "docs" / "security" / "cra-incident-response.md"
GUIDE_CATALOGS = ROOT / "frontend" / "src" / "i18n" / "guide"

PUBLIC_REPORT_URL = "https://github.com/AlphaHorizon-AI/Shogun/issues/new"
PRIVATE_REPORT_URL = (
    "https://github.com/AlphaHorizon-AI/Shogun/security/advisories/new"
)


def test_incident_reporting_is_the_final_reference_section() -> None:
    source = GUIDE.read_text(encoding="utf-8")
    navigation = source.split("const REFERENCE_SECTIONS = useMemo(() => [", 1)[
        1
    ].split("], []);", 1)[0]
    section_ids = re.findall(r"id: '([^']+)'", navigation)
    reference_branch = source.split("activeTab === 'reference' && (", 1)[1].split(
        "activeTab === 'architecture'", 1
    )[0]
    rendered_section_ids = re.findall(r'<section id="(ref-[^"]+)"', reference_branch)

    assert section_ids[-1] == "ref-incident-reporting"
    assert rendered_section_ids[-1] == "ref-incident-reporting"
    assert section_ids[-4:] == [
        "ref-maintenance",
        "ref-roles-responsibilities",
        "ref-modified-installations",
        "ref-incident-reporting",
    ]
    assert rendered_section_ids[-4:] == section_ids[-4:]
    assert [section_id for section_id in section_ids if section_id in rendered_section_ids] == (
        rendered_section_ids
    )
    assert source.index('id="ref-maintenance"') < source.index(
        'id="ref-incident-reporting"'
    )
    assert source.index('id="ref-incident-reporting"') < source.index(
        "activeTab === 'architecture'"
    )


def test_manual_defines_model_and_party_responsibility_boundaries() -> None:
    source = GUIDE.read_text(encoding="utf-8")
    section = source.split(
        '<section id="ref-roles-responsibilities"', 1
    )[1].split('<section id="ref-modified-installations"', 1)[0]

    assert "Roles &amp; Responsibilities" in section
    assert "Shogun is an orchestration framework—not an AI model" in section
    assert "does not bundle, train, or supply a proprietary LLM or foundation model" in section
    assert "not itself an LLM, foundation model, or general-purpose AI (GPAI) model" in section
    assert "model-agnostic" in section
    assert "Models may be cloud-hosted" in section
    assert "hosted locally by the organisation" in section
    assert "Alpha Horizon responsibilities" in section
    assert "Deploying organisation responsibilities" in section
    assert "Third-party model and service providers" in section
    assert "Regulatory roles follow the facts" in section
    assert "does not by itself determine the parties&apos; roles under the EU AI Act" in section
    assert "Alpha Horizon may have obligations as a provider or downstream provider" in section
    assert "Each party must assess and fulfil the duties attached to its actual role" in section
    assert "https://eur-lex.europa.eu/eli/reg/2024/1689/oj" in section
    assert "Nothing in this documentation excludes statutory rights or responsibilities" in section


def test_manual_defines_modified_installation_and_licence_boundaries() -> None:
    source = GUIDE.read_text(encoding="utf-8")
    section = source.split(
        '<section id="ref-modified-installations"', 1
    )[1].split('<section id="ref-incident-reporting"', 1)[0]

    assert "Modified Shogun Installations" in section
    assert "Internal modification is permitted only within the boundaries" in section
    assert "source-available—not open source" in section
    assert "sale, resale, rebranding, hosted or managed-service use" in section
    assert "public redistribution remain unchanged" in section
    assert "does not test, validate, certify, or warrant third-party modifications" in section
    assert "cannot legally exclude" in section
    assert "does not override any statutory rights" in section
    assert "https://github.com/AlphaHorizon-AI/Shogun/blob/main/LICENSE.md" in section


def test_manual_exposes_safe_public_and_private_reporting_routes() -> None:
    source = GUIDE.read_text(encoding="utf-8")

    assert 'Incident Reporting' in source
    assert f'href="{PUBLIC_REPORT_URL}"' in source
    assert f'href="{PRIVATE_REPORT_URL}"' in source
    assert 'contact@alphahorizon.io' in source
    assert 'rel="noopener noreferrer"' in source
    assert "Do <strong>not</strong> publish exploit code" in source
    assert "Opening a GitHub report notifies Alpha Horizon" in source
    assert "24 hours" in source
    assert "72 hours" in source
    assert "14 days" in source
    assert "one month" in source.lower()


def test_security_policy_and_cra_procedure_use_the_same_routes_and_clock() -> None:
    policy = SECURITY_POLICY.read_text(encoding="utf-8")
    procedure = CRA_PROCEDURE.read_text(encoding="utf-8")

    for document in (policy, procedure):
        assert PUBLIC_REPORT_URL in document
        assert PRIVATE_REPORT_URL in document
        assert "contact@alphahorizon.io" in document
        assert "24 hours" in document
        assert "72 hours" in document
        assert "14 days" in document
        assert "one month" in document.lower()

    assert "31 August 2031" not in policy
    assert "31 August 2031" not in procedure


def test_security_handling_is_law_bound_without_a_voluntary_fixed_end_date() -> None:
    guide_source = GUIDE.read_text(encoding="utf-8")
    guide_incident_section = guide_source.split(
        '<section id="ref-incident-reporting"', 1
    )[1].split("activeTab === 'architecture'", 1)[0]
    documents = {
        "Guide incident section": guide_incident_section,
        "SECURITY.md": SECURITY_POLICY.read_text(encoding="utf-8"),
        "CRA procedure": CRA_PROCEDURE.read_text(encoding="utf-8"),
    }

    for name, document in documents.items():
        normalized = " ".join(
            document.lower().replace("‑", "-").replace("–", "-").split()
        )
        assert "31 august 2031" not in normalized, name
        assert "official" in normalized, name
        assert "unmodified" in normalized, name
        assert (
            "security-vulnerability handling" in normalized
            or "security vulnerability handling" in normalized
            or "security vulnerability-handling" in normalized
        ), name
        assert (
            "not general technical support" in normalized
            or "not a general technical-support" in normalized
            or "does not include general technical support" in normalized
            or "separate from general customer support" in normalized
        ), name
        assert "helpdesk" in normalized, name
        assert "compatibility" in normalized, name
        assert "feature" in normalized, name
        assert "integration" in normalized, name
        assert (
            "modified build" in normalized
            or "third-party modification" in normalized
            or "customer or third-party modifications" in normalized
        ), name
        assert (
            "service-level agreement" in normalized
            or "service-level" in normalized
            or "an sla" in normalized
            or "sla," in normalized
        ), name
        assert "separate written agreement" in normalized, name
        assert "where required by applicable law" in normalized, name
        assert (
            "does not promise a patch for every report" in normalized
            or "does not promise that every reported issue will result in a patch" in normalized
        ), name


def test_statutory_retention_is_preserved_without_a_voluntary_blanket_term() -> None:
    policy = SECURITY_POLICY.read_text(encoding="utf-8")
    procedure = CRA_PROCEDURE.read_text(encoding="utf-8")

    for document in (policy, procedure):
        normalized = " ".join(document.lower().split())
        assert "no voluntary fixed retention period" in normalized
        assert "article 13(9)" in normalized
        assert "article 13(13)" in normalized
        assert "13(18)" in normalized
        assert "at least 10 years after issuance" in normalized
        assert "whichever is longer" in normalized
        assert "will remain available" not in normalized


def test_issue_chooser_routes_sensitive_reports_away_from_public_issues() -> None:
    config = yaml.safe_load(
        (ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml").read_text(
            encoding="utf-8"
        )
    )
    public_template_path = (
        ROOT / ".github" / "ISSUE_TEMPLATE" / "security-concern.yml"
    )
    public_template_source = public_template_path.read_text(encoding="utf-8")
    public_template = yaml.safe_load(public_template_source)

    assert config["blank_issues_enabled"] is False
    assert any(
        link["url"] == PRIVATE_REPORT_URL for link in config["contact_links"]
    )
    assert public_template["name"] == "Security concern (public and non-sensitive)"
    assert PRIVATE_REPORT_URL in public_template_source
    assert "This issue will be public" in public_template_source
    assert "I have removed secrets" in public_template_source


def test_all_guide_catalogs_have_the_same_keys() -> None:
    catalogs = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in GUIDE_CATALOGS.glob("*.json")
    }
    assert "en" in catalogs
    expected = set(catalogs["en"])
    extracted = set(extract_fragments(GUIDE.read_text(encoding="utf-8")))
    assert expected == extracted
    assert "Incident Reporting" in expected
    assert "Public, non-sensitive reports" in expected

    for language, catalog in catalogs.items():
        assert set(catalog) == expected, f"Guide catalog drift for {language}"


def test_yellow_label_guide_omits_removed_product_features() -> None:
    source = GUIDE.read_text(encoding="utf-8")

    for removed_feature in (
        "Flow Stack",
        "Team Mode",
        "Microsoft Teams",
        "ref-teams",
        "ref-logs",
        "Nexus",
        "Gensui",
    ):
        assert removed_feature not in source
