from __future__ import annotations

import json

import pytest

from shogun.engine import flow_engine
from shogun.services.structured_transformations import try_deterministic_matrix_transform

TASK = """Read the complete SAP report.
For every order where Sa = 06, create one production row using Soll-Menge.
For every order where Sa = 01, aggregate Rest-Menge by Starttermin Jahr/Mo.
Create one stock row when Bestand is greater than zero. Do not create duplicate production-order rows.
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


def test_sap_adapter_uses_start_month_and_deduplicates_business_rows():
    result = try_deterministic_matrix_transform(
        task_description=TASK,
        source_context=SOURCE,
        fixed_context=FIXED_CONTEXT,
    )

    assert result is not None
    assert result.adapter_id == "sap_disposition_v1"
    assert len(result.rows) == 3
    assert all(len(row) == 22 for row in result.rows)

    stock, production, demand = result.rows
    assert stock[:6] == ["Kolben-UT P MS0.410", "140052", "59439-01", "", "Lager 0031", 1]
    assert production[:6] == ["Kolben-UT P MS0.410", "140052", "59439-01", "", "20164627", 51]
    assert demand[20] == 50  # Starttermin 2027/05 -> column U.
    assert demand[19] == ""  # Endtermin 2027/04 must not be used.
    assert demand[21] == ""  # Starttermin 2027/07 is outside the template horizon.


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
    assert demand[12] == 611
    assert demand[16] == 1200
    assert demand[18:22] == [1200, 1200, 1200, 1200]


def test_sap_coverage_counts_unique_orders():
    assert flow_engine._expected_sap_output_rows(SOURCE, TASK) == 3


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
    assert len(rows) == 3
    assert progress[-1][0] == progress[-1][1]
