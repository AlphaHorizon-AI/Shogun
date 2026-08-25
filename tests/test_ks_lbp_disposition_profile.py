"""KS-LBP rules remain profile-local; article numbers are regression fixtures only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shogun.services.private_transformation_profiles import (
    PrivateTransformationProfileService,
)
from shogun.services.structured_transformations import (
    try_deterministic_matrix_transform,
)

ROOT = Path(__file__).resolve().parents[1]
DEFINITION_PATH = ROOT / "profiles" / "ks-lbp" / "ks_lbp_disposition_v3.definition.json"
PORTABLE_PATH = ROOT / "profiles" / "ks-lbp" / "ks_lbp_disposition_v3.shogun-profile.json"
V4_DEFINITION_PATH = ROOT / "profiles" / "ks-lbp" / "ks_lbp_disposition_v4.definition.json"
V4_PORTABLE_PATH = ROOT / "profiles" / "ks-lbp" / "ks_lbp_disposition_v4.shogun-profile.json"

FIXED_CONTEXT = """[FILE TEMPLATE CONTRACT]
Format: xlsx
[MACHINE-READABLE TEMPLATE MANIFEST]
{"kind":"excel","sheets":[{"logical_columns":24,"preview_rows":[
  [null,"Artikel-Nr","Rohling","Rohteil","Fertigungsauftrag",null,
   "Kunde","Bemerkung","Avo","MD04/SAP","Rückstand","2026-07-01",
   "2026-08-01",">= 2026-09-01",null,null,null,null,null,null,null,null,null,null]
]}]}
"""


def _profile() -> dict:
    return json.loads(DEFINITION_PATH.read_text(encoding="utf-8"))


def _v4_profile() -> dict:
    return json.loads(V4_DEFINITION_PATH.read_text(encoding="utf-8"))


def _built_section(
    parent: str,
    unterteil: str,
    oberteil: str,
    *,
    bom_lines: list[tuple[str, str]] | None = None,
    requirements: list[tuple[str, int, int, str]] | None = None,
) -> str:
    lines = bom_lines or [
        (oberteil, "Kolben-OT ST TEST.411"),
        (unterteil, "Kolben-UT G TEST.410"),
        ("PACK-1", "Verpackung"),
    ]
    records = requirements or [("request-1", 25, 999, "2026/08")]
    bom = "\n".join(
        f"{index:04d} {article} {description} 1,000 ST" for index, (article, description) in enumerate(lines, start=10)
    )
    record_text = "\n".join(
        f"01 {parent} {reference} 2026/07 2026/07 {start_month} {start_month} {planned} {remaining} 25.08.2026"
        for reference, planned, remaining, start_month in records
    )
    return f"""Sachnummer : {parent}
Teilebez. : Kolben geb. TEST410/TEST411 Werkstoff : GGG
Bestand : 0
Stückliste :
Pos Material Bezeichnung Menge ME
{bom}
Bemerkungen :
Sa Artikelnummer Auftrag Endtermin Starttermin Soll-Menge Rest-Menge Termin
Endtermin Starttermin
{record_text}
"""


def _stock_section(article: str, description: str) -> str:
    return f"""Sachnummer : {article}
Teilebez. : {description} Werkstoff : TEST
Bestand : 1
Stückliste :
Pos Material Bezeichnung Menge ME
Bemerkungen :
Sa Artikelnummer Auftrag Endtermin Starttermin Soll-Menge Rest-Menge Termin
Endtermin Starttermin
"""


def test_portable_profile_contains_the_reviewed_definition_without_fixture_ids():
    definition_text = DEFINITION_PATH.read_text(encoding="utf-8")
    portable = json.loads(PORTABLE_PATH.read_text(encoding="utf-8"))

    assert portable["format"] == "shogun.private-transformation-profile"
    assert portable["profile"] == json.loads(definition_text)
    imported = PrivateTransformationProfileService().import_document(portable)
    assert imported["profile_reference"]["id"] == "ks_lbp_disposition_v3"
    for fixture_only_id in ("140022", "140023", "140024", "140273", "140274", "140275"):
        assert fixture_only_id not in definition_text


def test_known_built_pistons_keep_both_components_and_preserve_soll_records():
    source = "\n".join(
        [
            _built_section(
                "140024",
                "140022",
                "140023",
                requirements=[
                    ("request-1", 25, 7, "2026/08"),
                    ("request-2", 25, 3, "2026/08"),
                ],
            ),
            _built_section("140273", "140274", "140275"),
        ]
    )

    rows = try_deterministic_matrix_transform(
        profile=_profile(),
        source_context=source,
        fixed_context=FIXED_CONTEXT,
    ).rows

    first_parent_rows = [row for row in rows if row[1] == "140024"]
    second_parent_rows = [row for row in rows if row[1] == "140273"]
    assert len(first_parent_rows) == 2
    assert all(row[2] == "140022 // 140023" and row[3] == "" for row in first_parent_rows)
    assert [row[12] for row in first_parent_rows] == [25, 25]
    assert sum(row[12] for row in first_parent_rows) == 50
    assert len(second_parent_rows) == 1
    assert second_parent_rows[0][2] == "140274 // 140275"


def test_material_groups_sort_deterministically_instead_of_preserving_source_order():
    source = "\n".join(
        [
            _stock_section("GGG-X", "Kolben G TEST.001"),
            _stock_section("IAM-X", "ESG-Kolben TEST.002"),
            _stock_section("S-X", "Kolben S TEST.003 Ro Ri"),
        ]
    )

    rows = try_deterministic_matrix_transform(
        profile=_profile(),
        source_context=source,
        fixed_context=FIXED_CONTEXT,
    ).rows

    assert [row[1] for row in rows] == ["S-X", "GGG-X", "IAM-X"]


def test_unclassified_ks_lbp_section_fails_closed():
    with pytest.raises(ValueError, match="could not classify section.*UNKNOWN-X"):
        try_deterministic_matrix_transform(
            profile=_profile(),
            source_context=_stock_section("UNKNOWN-X", "Unknown material"),
            fixed_context=FIXED_CONTEXT,
        )


def test_v4_portable_profile_is_integrity_locked_and_importable():
    portable = json.loads(V4_PORTABLE_PATH.read_text(encoding="utf-8"))

    imported = PrivateTransformationProfileService().import_document(portable)

    assert portable["profile"] == _v4_profile()
    assert imported["profile_reference"]["id"] == "ks_lbp_disposition_v4"


def test_v4_resolves_declared_variants_and_golden_reference_exceptions():
    source = "\n".join(
        [
            _built_section(
                "45132100",
                "99250100",
                "45131100",
                bom_lines=[
                    ("99250100", "Kolben-UT G 270.011+"),
                    ("45131100", "Kolben-OT ST 270.010"),
                    ("45131150", "Kolben-OT ST 270.010"),
                    ("45131180", "Kolben-OT ST 270.010"),
                ],
            ),
            _built_section(
                "45994100-52",
                "MISSING-UT",
                "45993100",
                bom_lines=[("45993100", "Kolben-OT ST 350.026")],
            ),
            _built_section(
                "45994100-53",
                "MISSING-UT",
                "MISSING-OT",
                bom_lines=[("PACK-X", "Verpackung")],
            ),
            _built_section(
                "68715180",
                "MISSING-UT",
                "MISSING-OT",
                bom_lines=[("68715170", "Kolben geb. G200.065/ST200.070")],
            ),
            _built_section(
                "68989200",
                "68957200",
                "68988200",
                bom_lines=[
                    ("68957200", "Kolben-UT G 250.097++"),
                    ("68957280", "Kolben-UT G 250.097++"),
                    ("68988200", "Kolben-OT ST 250.098"),
                ],
            ),
            _built_section(
                "99176300-50",
                "MISSING-UT",
                "MISSING-OT",
                bom_lines=[("PACK-Y", "Verpackung")],
            ),
        ]
    )

    rows = try_deterministic_matrix_transform(
        profile=_v4_profile(),
        source_context=source,
        fixed_context=FIXED_CONTEXT,
    ).rows
    relationships = {str(row[1]): row[2] for row in rows}

    assert relationships["45132100"] == "99250100 // 45131100"
    assert relationships["45994100-52"] == "45143300 // 45179100 (alt)"
    assert "45994100-53" not in relationships
    assert relationships["68715180"] == "68715170"
    assert relationships["68989200"] == "68957200 // 68988200"
    assert relationships["99176300-50"] == ""


@pytest.mark.parametrize(
    ("bom_lines", "role", "count"),
    [
        ([("LOWER-X", "Kolben-UT G TEST.410")], "oberteil", 0),
        (
            [
                ("LOWER-X", "Kolben-UT G TEST.410"),
                ("UPPER-X", "Kolben-OT ST TEST.411"),
                ("UPPER-Y", "Kolben-OT ST TEST.411"),
            ],
            "oberteil",
            2,
        ),
    ],
)
def test_built_piston_role_matching_fails_closed_for_any_article(
    bom_lines,
    role,
    count,
):
    source = _built_section(
        "PARENT-X",
        "LOWER-X",
        "UPPER-X",
        bom_lines=bom_lines,
    )

    with pytest.raises(
        ValueError,
        match=rf"selector '{role}'.*PARENT-X.*found {count}",
    ):
        try_deterministic_matrix_transform(
            profile=_profile(),
            source_context=source,
            fixed_context=FIXED_CONTEXT,
        )
