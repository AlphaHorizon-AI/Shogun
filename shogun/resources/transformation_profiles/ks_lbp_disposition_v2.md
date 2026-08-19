# SAP Disposition PDF to Excel — Profile v2 Contract

Read every connected SAP disposition PDF and return only one JSON two-dimensional array matching the connected Excel template.

## Output contract

- Every row must use the template's complete logical width. The current KS-LBP template is 24 columns, A:X.
- Use `""` for blank cells.
- Return no objects, Markdown, prose, headings, summaries, or code fences.
- Treat the deterministic transformation profile as authoritative. If its source or template validation fails, stop instead of guessing.

The current column contract is:

1. A — `Teilebez.`
2. B — `Sachnummer` / Artikel-Nr
3. C — Rohling
4. D — Rohteil
5. E — Fertigungsauftrag or `Lager 0031`
6. F — quantity
7. G — Kunde
8. H — Bemerkung
9. I — Avo
10. J — MD04/SAP
11. K — Rückstand
12. L through W — Jul 2026 through Jun 2027
13. X — `>= Jul 2027`

Always validate and use the actual template manifest rather than assuming that another workbook has the same width, horizon, or positions.

## SAP semantics

- A material begins at `Sachnummer : <article number>`; preserve suffixes such as `-01`.
- Extract `Teilebez.`, `Bestand`, relevant BOM components, and every `Sa = 01` and `Sa = 06` record.
- Source reports may print the date columns as either `Starttermin Endtermin` or `Endtermin Starttermin`.
- Bind the closest preceding header labels before reading date values. Never infer Starttermin from a fixed position.
- A missing, incomplete, duplicated, unknown, or ambiguous date header is an error.

For each material, emit rows in this order:

1. One stock row when `Bestand > 0`: E = `Lager 0031`, F = Bestand.
2. One production row per unique `Sa = 06` article + Auftrag identity: E = Auftrag without leading zeroes, F = Soll-Menge.
3. One planning row when `Sa = 01` demand exists.

For `Sa = 01`:

- demand month = semantic `Starttermin Jahr/Mo`
- demand quantity = `Rest-Menge`
- before the first explicit month → backlog column
- exact in-horizon month → matching month column
- at or after the future threshold → future column

Aggregate all demand quantities for the same material and destination bucket. Every source quantity must be accounted for exactly once; never drop or shift an unmapped month.

For BOM mapping, select the relevant Rohling and Rohteil/halbzeug/vorbearbeitet component and exclude packaging, boxes, bags, pins, nozzles, and other auxiliary parts.

Before returning, verify the template width, unique production identities, exact source accounting, numeric quantities, and that planning values occur only in planning columns.
