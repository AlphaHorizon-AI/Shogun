from __future__ import annotations

import json

import pytest

from shogun.engine import flow_engine
from shogun.services.structured_transformations import try_deterministic_matrix_transform

TASK = """Read the complete SAP report.
For every order where Sa = 06, create one production row using Soll-Menge.
For every order where Sa = 01, aggregate Rest-Menge by Endtermin Jahr/Mo, never Starttermin Jahr/Mo.
Create one stock row when Bestand is greater than zero. Preserve every source order occurrence.
Return every relevant record as a two-dimensional array with exactly 22 values per row.
"""

FIXED_CONTEXT = """[FILE TEMPLATE CONTRACT]
Format: xlsx
[MACHINE-READABLE TEMPLATE MANIFEST]
{"kind":"excel","sheets":[{"logical_columns":22,"preview_rows":[
  [null,"Artikel-Nr","Rohling","Rohteil","Fertigungsauftrag",null,"Kunde","Bemerkung","Avo","MD04/SAP",
   "2026-07-01T00:00:00","2026-08-01T00:00:00","2026-09-01T00:00:00","2026-10-01T00:00:00",
   "2026-11-01T00:00:00","2026-12-01T00:00:00","2027-01-01T00:00:00","2027-02-01T00:00:00",
   "2027-03-01T00:00:00","2027-04-01T00:00:00","2027-05-01T00:00:00","2027-06-01T00:00:00"]
]}]}
"""

FULL_HORIZON_CONTEXT = """[FILE TEMPLATE CONTRACT]
Format: xlsx
[MACHINE-READABLE TEMPLATE MANIFEST]
{"kind":"excel","sheets":[{"logical_columns":24,"preview_rows":[
  [null,"Artikel-Nr","Rohling","Rohteil","Fertigungsauftrag",null,"Kunde","Bemerkung","Avo","MD04/SAP",
   "Rückstand","2026-07-01T00:00:00","2026-08-01T00:00:00","2026-09-01T00:00:00",
   "2026-10-01T00:00:00","2026-11-01T00:00:00","2026-12-01T00:00:00","2027-01-01T00:00:00",
   "2027-02-01T00:00:00","2027-03-01T00:00:00","2027-04-01T00:00:00","2027-05-01T00:00:00",
   "2027-06-01T00:00:00",">= Jul 2027"]
]}]}
"""

SOURCE = """Sachnummer : 140052 Disponent : 40 A. Schmitt_OT&UT Nachfolgematerial :
Teilebez. : Kolben-UT P MS0.410 Werkstoff : GGG 70 Zeichnung : 65.1000. 00
Bestand : 1,0 KT-Bestand : 0,0
Stückliste : Pos Materialnummer Benennung Menge ME Basismenge : 1,000
 0010 59439-01 Rohling MS0410 vorbearbeitet 1,000 ST
 0040 70798 Spannstift CONNEX Typ S 1,000 ST
Bemerkungen :
Sa Artikelnummer Best-Nr Auftrag Lief Jahr/WW Jahr/MO Jahr/WW Jahr/Mo Soll-Menge Rest-Menge Datum
Endtermin Starttermin
06 140052 0020164627 2026/35 2026/08 2026/35 2026/08 51,0 50,0 21.07.2026
06 140052 0020164627 2026/35 2026/08 2026/35 2026/08 51,0 50,0 21.07.2026
01 140052 0003946433 2027/16 2027/04 2027/18 2027/05 52,0 50,0 21.07.2026
01 140052 0003950611 2027/23 2027/06 2027/25 2027/07 176,0 175,0 21.07.2026
"""

GROUPED_NUMBER_SOURCE = """Sachnummer : 68420100 Disponent : 40 A. Schmitt_OT&UT Nachfolgematerial :
Teilebez. : Kolben STU190.037/ST190.041 CR10.5 Werkstoff : 42 CRMO 4 V Zeichnung : 13171.189523. 06
Bestand : 0,0 KT-Bestand : 0,0
Stückliste : Pos Materialnummer Benennung Menge ME Basismenge : 1,000
 0010 68420050 Kolben STU190 vorbearbeitet 1,000 ST
Bemerkungen :
Sa Artikelnummer Best-Nr Auftrag Lief Jahr/WW Jahr/MO Jahr/WW Jahr/Mo Soll-Menge Rest-Menge Datum
Endtermin Starttermin
01 68420100 0003955053 2026/34 2026/08 2026/37 2026/09 624,0 611,0 21.07.2026
01 68420100 0003955056 2026/47 2026/11 2027/01 2027/01 1 224,0 1 200,0 21.07.2026
01 68420100 0003955058 2027/03 2027/01 2027/09 2027/03 1 224,0 1 200,0 21.07.2026
01 68420100 0003955059 2027/07 2027/02 2027/13 2027/04 1 224,0 1 200,0 21.07.2026
01 68420100 0003955060 2027/12 2027/03 2027/18 2027/05 1.224,0 1.200,0 21.07.2026
01 68420100 0003955061 2027/16 2027/04 2027/22 2027/06 1 224,0 1 200,0 21.07.2026
"""

END_MONTH_SOURCE = """--- Page 1 ---
Sachnummer : 140090 Disponent : 40 A. Schmitt_OT&UT Nachfolgematerial :
Teilebez. : Kolben-OT ST VS0.211 Werkstoff : Stahl Zeichnung : 1
Bestand : 0,0 KT-Bestand : 0,0
Stückliste : Pos Materialnummer Benennung Menge ME Basismenge : 1,000
 0010 140089 Rohling Kolben 1,000 ST
Bemerkungen :
Sa Artikelnummer Best-Nr Auftrag Lief Jahr/WW Jahr/MO Jahr/WW Jahr/Mo Soll-Menge Rest-Menge Datum
Endtermin Starttermin
01 140090 0003943422 2026/43 2026/10 2026/45 2026/11 30,0 29,0 21.07.2026
"""

DUPLICATE_DEMAND_SOURCE = """Sachnummer : 68766100 Disponent : 40 A. Schmitt_OT&UT Nachfolgematerial :
Teilebez. : Kolben Test Werkstoff : Stahl Zeichnung : 1
Bestand : 0,0 KT-Bestand : 0,0
Stückliste : Pos Materialnummer Benennung Menge ME Basismenge : 1,000
 0010 68766000 Rohling Kolben 1,000 ST
Bemerkungen :
Sa Artikelnummer Best-Nr Auftrag Lief Jahr/WW Jahr/MO Jahr/WW Jahr/Mo Soll-Menge Rest-Menge Datum
Endtermin Starttermin
01 68766100 0044344787 2026/43 2026/10 2026/45 2026/11 100,0 100,0 21.07.2026
01 68766100 0044344787 2026/43 2026/10 2026/45 2026/11 100,0 100,0 21.07.2026
01 68766100 0044344999 2026/43 2026/10 2026/46 2026/11 25,0 25,0 21.07.2026
"""

FULL_HORIZON_SOURCE = END_MONTH_SOURCE.replace(
    "01 140090 0003943422 2026/43 2026/10 2026/45 2026/11 30,0 29,0 21.07.2026",
    "01 140090 0003943421 2026/24 2026/06 2026/24 2026/06 6,0 5,0 21.07.2026\n"
    "01 140090 0003943422 2026/28 2026/07 2026/28 2026/07 8,0 7,0 21.07.2026\n"
    "01 140090 0003943423 2027/24 2027/06 2027/24 2027/06 12,0 11,0 21.07.2026\n"
    "01 140090 0003943424 2027/28 2027/07 2027/28 2027/07 14,0 13,0 21.07.2026\n"
    "01 140090 0003943425 2029/36 2029/09 2029/36 2029/09 18,0 17,0 21.07.2026",
)


def test_sap_adapter_uses_end_month_and_preserves_business_row_occurrences():
    result = try_deterministic_matrix_transform(
        task_description=TASK,
        source_context=SOURCE,
        fixed_context=FIXED_CONTEXT,
    )

    assert result is not None
    assert result.adapter_id == "sap_disposition_v1"
    assert len(result.rows) == 4
    assert all(len(row) == 22 for row in result.rows)

    stock, production, repeated_production, demand = result.rows
    assert stock[:6] == ["Kolben-UT P MS0.410", "140052", "59439-01", "", "Lager 0031", 1]
    assert production[:6] == ["Kolben-UT P MS0.410", "140052", "59439-01", "", "20164627", 51]
    assert repeated_production == production
    assert demand[19] == 50  # Endtermin 2027/04 -> column T.
    assert demand[20] == ""  # Starttermin 2027/05 must not be used.
    assert demand[21] == 175  # Endtermin 2027/06, even though Starttermin is outside the horizon.


def test_sap_adapter_maps_rest_quantity_to_endtermin_month_for_legacy_saved_flow():
    legacy_task = TASK.replace(
        "Endtermin Jahr/Mo, never Starttermin Jahr/Mo",
        "Starttermin Jahr/Mo",
    )

    result = try_deterministic_matrix_transform(
        task_description=legacy_task,
        source_context=END_MONTH_SOURCE,
        fixed_context=FIXED_CONTEXT,
    )

    assert result is not None
    demand = result.rows[0]
    assert demand[13] == 29  # 2026/10 from Endtermin.
    assert demand[14] == ""  # 2026/11 from Starttermin must remain blank.


def test_sap_adapter_sums_every_identical_demand_occurrence_by_endtermin_month():
    result = try_deterministic_matrix_transform(
        task_description=TASK,
        source_context=DUPLICATE_DEMAND_SOURCE,
        fixed_context=FIXED_CONTEXT,
    )

    assert result is not None
    assert len(result.rows) == 1
    demand = result.rows[0]
    assert demand[13] == 225
    assert demand[14] == ""


def test_sap_adapter_creates_materials_only_from_explicit_sachnummer_headers():
    source = END_MONTH_SOURCE.replace(
        "0010 140089 Rohling Kolben",
        "0010 68859100 Rohling Kreuzkopf BG500 Ø 520",
    )

    result = try_deterministic_matrix_transform(
        task_description=TASK,
        source_context=source,
        fixed_context=FIXED_CONTEXT,
    )

    assert result is not None
    assert {row[1] for row in result.rows} == {"140090"}
    assert all(row[1] != "68859100" for row in result.rows)


def test_sap_adapter_keeps_material_context_across_page_breaks():
    source = END_MONTH_SOURCE.replace(
        "Bemerkungen :\nSa Artikelnummer",
        "Bemerkungen :\n--- Page 2 ---\n1.Periode 2.Periode Bedarf Bestand Bestellt\nSa Artikelnummer",
    )

    result = try_deterministic_matrix_transform(
        task_description=TASK,
        source_context=source,
        fixed_context=FIXED_CONTEXT,
    )

    assert result is not None
    assert result.rows[0][1] == "140090"
    assert result.rows[0][13] == 29


def test_sap_adapter_accumulates_later_endtermin_months_in_explicit_future_bucket():
    fixed_context = FIXED_CONTEXT.replace(
        '"2027-05-01T00:00:00","2027-06-01T00:00:00"]',
        '"2027-05-01T00:00:00","2027-06-01T00:00:00",">= Jul 2027"]',
    ).replace('"logical_columns":22', '"logical_columns":23')
    source = END_MONTH_SOURCE.replace(
        "01 140090 0003943422 2026/43 2026/10 2026/45 2026/11 30,0 29,0 21.07.2026",
        "01 140090 0003943422 2027/31 2027/08 2027/33 2027/08 30,0 29,0 21.07.2026\n"
        "01 140090 0003943423 2027/35 2027/09 2027/36 2027/09 12,0 11,0 21.07.2026",
    )

    result = try_deterministic_matrix_transform(
        task_description=TASK.replace("22 values", "23 values"),
        source_context=source,
        fixed_context=fixed_context,
    )

    assert result is not None
    assert len(result.rows[0]) == 23
    assert result.rows[0][22] == 40


def test_sap_adapter_routes_every_rest_quantity_into_exactly_one_full_horizon_bucket():
    result = try_deterministic_matrix_transform(
        task_description=TASK.replace("22 values", "24 values"),
        source_context=FULL_HORIZON_SOURCE,
        fixed_context=FULL_HORIZON_CONTEXT,
    )

    assert result is not None
    assert len(result.rows) == 1
    demand = result.rows[0]
    assert len(demand) == 24
    assert demand[10] == 5  # Endtermin before July 2026 -> Rückstand.
    assert demand[11] == 7  # July 2026 remains in its exact month.
    assert demand[22] == 11  # June 2027 remains in its exact month.
    assert demand[23] == 30  # July 2027 and September 2029 -> future bucket.
    assert sum(value for value in demand[10:24] if isinstance(value, (int, float))) == 53


def test_sap_adapter_fails_closed_when_template_cannot_account_for_a_demand_month():
    source = END_MONTH_SOURCE.replace(
        "01 140090 0003943422 2026/43 2026/10 2026/45 2026/11 30,0 29,0 21.07.2026",
        "01 140090 0003943422 2026/24 2026/06 2026/24 2026/06 30,0 29,0 21.07.2026",
    )

    with pytest.raises(ValueError, match="2026/06.*no Excel planning bucket"):
        try_deterministic_matrix_transform(
            task_description=TASK,
            source_context=source,
            fixed_context=FIXED_CONTEXT,
        )


def test_sap_adapter_places_semifinished_bom_material_in_rohteil():
    source = (
        SOURCE
        + """
Sachnummer : 99288100 Disponent : 40 A. Schmitt_OT&UT Nachfolgematerial :
Teilebez. : Kolben-OT ST 460.012 Lasercladding Werkstoff : 42 CRMO 4 V Zeichnung : 1
Bestand : 0,0 KT-Bestand : 0,0
Stückliste : Pos Materialnummer Benennung Menge ME Basismenge : 1,000
 0010 99288050 Kolben-OT ST 460.012 Lasercladding 1,000 ST
Bemerkungen :
Sa Artikelnummer Best-Nr Auftrag Lief Jahr/WW Jahr/MO Jahr/WW Jahr/Mo Soll-Menge Rest-Menge Datum
Endtermin Starttermin
01 99288100 0003929674 2027/25 2027/06 2027/26 2027/06 14,0 13,0 21.07.2026
"""
    )

    result = try_deterministic_matrix_transform(
        task_description=TASK,
        source_context=source,
        fixed_context=FIXED_CONTEXT,
    )

    assert result is not None
    row = next(row for row in result.rows if row[1] == "99288100")
    assert row[2] == ""
    assert row[3] == "99288050"
    assert row[21] == 13


def test_sap_adapter_parses_grouped_german_quantities_without_splitting_fields():
    result = try_deterministic_matrix_transform(
        task_description=TASK,
        source_context=GROUPED_NUMBER_SOURCE,
        fixed_context=FIXED_CONTEXT,
    )

    assert result is not None
    assert len(result.rows) == 1
    demand = result.rows[0]
    assert demand[11] == 611
    assert demand[14] == 1200
    assert demand[16:20] == [1200, 1200, 1200, 1200]
    assert demand[20:22] == ["", ""]


def test_sap_coverage_counts_source_order_occurrences():
    assert flow_engine._expected_sap_output_rows(SOURCE, TASK) == 4


@pytest.mark.asyncio
async def test_samurai_uses_deterministic_adapter_without_model_routing(monkeypatch):
    async def unexpected_route(*_args, **_kwargs):
        raise AssertionError("deterministic transformation must not route to a model")

    monkeypatch.setattr(flow_engine, "_resolve_task_llm_chain", unexpected_route)
    progress: list[tuple[int, int]] = []

    async def report(completed: int, total: int):
        progress.append((completed, total))

    output = await flow_engine._exec_samurai(
        {"task_description": TASK},
        SOURCE,
        progress_callback=report,
        fixed_context_str=FIXED_CONTEXT,
    )

    rows = json.loads(output)
    assert len(rows) == 4
    assert progress[-1][0] == progress[-1][1]
