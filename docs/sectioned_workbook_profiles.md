# Private profiles for sectioned workbook updates

The Files node's `excel_create` action accepts `workbook_transform`: a portable private
`profile_path`, an existing `template_path`, one to ten `pdf_paths`, and optional `sheet_name`,
`reference_workbook_path` and extraction `options`. Paths stay inside the Shogun workspace.
The existing Office mode gate applies. Import verifies the profile's schema and content hash;
importing a file does not publish it or activate a saved flow.

## Configure an AgentFlow

In a Files node, select **Excel — Create**, then choose **Update existing workbook
from PDFs** under **Excel operation**. Select the rules file, the existing Excel
workbook, one to ten original PDFs, and optionally a reference workbook. All these
files must be inside the Shogun workspace; the browse buttons select workspace files.
Set a new destination folder and filename. The sheet name may be left empty to use
the profile's worksheet. An explicitly selected workbook takes priority over an
upstream File Template.

Connect **Input → Files → Output** for this operation. The Files node reads the
configured PDFs directly.

Alternatively, attach the private workbook profile to a **Samurai** node. Connect
exactly one Excel **File Template** and one to ten **Files — PDF Read** nodes
directly to that Samurai, then connect it directly to one **Files — Excel Create**
writer and an Output node. Use full-document PDF reads, without a page range.
The writer uses **Create from previous step** with a new destination filename;
leave its separate PDF workbook controls unconfigured. The private rules select
the worksheet. Use an empty File Template for `populate_template` and a filled
planning workbook for `update_existing`.

The Samurai validates the pinned private rules and connected files. Its Files
writer then runs the same page-aware parser and workbook checks as the direct
operation. The job belongs to that run and writer, and refuses changed inputs.
Model responses, document text and saved run summaries cannot create executable
workbook jobs. Workbook profiles never fall back to model-generated row matrices.
The private profile supplies the executable mapping; changing free-text task
instructions alone does not change those rules. Existing document-extraction
profiles continue to use their normal Samurai path.

## Profile rules

Profiles use the existing `sectioned_record_matrix_v1` adapter and its parsing/value primitives.
`parameters.workbook_update` adds preservation-oriented updates to an existing workbook.
It uses **one-based** Excel row and column numbers. This differs from the existing matrix
adapter's zero-based `row_rules.columns` indexes.

Configure the header row, first data row, section key column, expected headers and record rules.
Each record rule can specify an exact reference column, insertion values, and optional date
and quantity fields. Dates, quantities and monthly columns are unnecessary for a text-only
workflow. Tests demonstrate maintenance notes with headers on row 3, data starting on row 5,
the asset key in D, the reference in B and notes in F; another test uses maintenance hours
and ISO due dates with different columns.

Reuse `literal`, `section_key`, `field`, `group`, `case`, `coalesce` and `join` value specs.
Conversions use `value_type`, including `number`, `strict_localized_number`,
`strict_localized_float`, `iso_date` and `calendar_week_monday`. Strict localized numbers
interpret comma decimals and grouped thousands; use `number` for dot decimals.

### Populate an empty template

Set `workbook_update.mode` to `populate_template` when the input workbook contains
headers and formatting only. The default, `update_existing`, continues to require
existing section groups and preserves planner-maintained values.

Template population reads the section identifiers from the current PDFs and creates
their rows at `data_start_row`. No list of known identifiers or populated reference
workbook is required. It rejects any existing value below the headers, so it cannot
silently duplicate or replace a populated plan. Use the original empty template for
each fresh run and choose a separate output file.

`template_section_values` maps section-level fields into a heading row for each
section. The engine always writes its identifier in `section_key_column`. Existing
section and record rules then create stock/task/order/detail rows. Even sections
whose records need review retain their heading row. `template_section_sort` accepts
up to eight value specifications, compared in order, for configured group ranks,
numeric sizes and identifiers. Missing sort values follow known values. Sorting is
applied only during empty-template population, not to an existing plan.

By default, `template_section_row_policy` is `always`, so that heading remains a
separate row. Set it to `merge_first_detail` to fold the section values into the
first generated stock, order or record row when every overlapping nonblank value is
equal. The `CREATED_SECTION` audit event then points to that shared physical row.
Sections without a generated detail still retain their heading. If a section value
would overwrite a different nonblank detail value, the engine keeps both rows and
emits `SECTION_ROW_MERGE_CONFLICT` for review. This mode is available only with
`populate_template`.

The existing `parameters.section_order` rules can additionally place referenced
sections before their parents, using `dependencies_before.fields`. This is applied
after the numeric/text sort and only to selected sections. Excluded dependencies
remain excluded and accounted for in the audit. Duplicate selected keys, cycles,
or an ordering rule that drops a selected section fail before publication.

When the selected business scope also includes referenced sections, configure
`parameters.section_selection_dependencies` separately. Its `fields` list names
section fields containing exact section identifiers. `transitive` controls whether
the engine follows only references from the original selection or the complete
reachable chain. `missing` is `ignore` or `error`; ignored references remain visible
as `IGNORED_MISSING_SELECTION_DEPENDENCY` audit events. Included sections produce
`INCLUDED_DEPENDENCY_SECTION` events and retain all of their source records. Matching
is exact and source-driven, so profiles do not need fixed material or asset lists.
Referenced duplicate keys and reachable cycles fail before publication.

```json
"section_selection_dependencies": {
  "fields": ["component", "subcomponent"],
  "transitive": true,
  "missing": "ignore"
}
```

Generated rows use the formatting and row height at `data_start_row`; the original
headers, blank formatted rows and all other sheets remain preserved.

### Planning columns

The month headings define the current dates; the rules need not contain fixed months.
Optional `backlog_headers` declares exact labels for dates before the first visible
month. Optional `future_header_patterns` identifies headers such as `>= Sep 2028`;
the date in that header defines the threshold. These use the existing monthly bucket
resolver. Each record still receives its own row, including when several records
map to the same bucket. Unsupported labels and duplicate buckets remain errors.

`require_date_in_planning_horizon` (and its legacy alias
`require_planning_horizon`) uses only the exact dated month headers to define the
allowed range. A record before, after or in a missing month inside that range is
reported as `OUTSIDE_PLANNING_HORIZON`, even when a backlog or future catch-all
could accept it. A rule that enables `planning_month_quantity` without either
explicit horizon flag retains the catch-all behavior.

By default, the engine derives that planning month from `date_spec`. Set
`planning_month_spec` when the source has a separate bucket month. It may resolve to
`YYYY/MM`, `YYYY-MM`, `YYYY/MM/DD`, or a date/datetime value (for example through
`value_type: "iso_date"`). The resolved month drives both `planning_month_quantity`
and exact-horizon filtering, while `date_spec` still supplies the record's exact
date. A missing, malformed or impossible planning month produces
`AMBIGUOUS_DATE_MAPPING`; the engine does not fall back to `date_spec` when an
explicit `planning_month_spec` is present.

Keep workflow policy explicit:

- `source_identity_fields` identifies a source record independently of PDF page/order.
- Reference matching preserves leading zeros unless `match_strip_leading_zeros` is true.
- Existing quantity/date cells are filled only when blank. Nonblank values, including zero,
  remain under planner control.
- A section rule's `policy` defaults to `fill_blank`; `replace` explicitly permits replacement.
- `alternative_quantity_spec` holds disagreement for review instead of choosing a value.
- `require_date_in_planning_horizon` filters against exact dated month headers.
  `planning_month_quantity` additionally writes the quantity into that month's cell.
- `planning_month_spec` optionally selects that month from a source value separate
  from the exact `date_spec` value.
- `when` uses the existing section conditions, for example
  `{"field": "zone", "operator": "equals", "value": "A"}`.

The engine preserves baseline cells and formatting, rejects ambiguous record placement,
and retains one disposition per source record. Reports include normalized source records,
the audit, permitted changes, and a preservation comparison. A reference workbook with a
compatible layout can supply row comparison metrics; a prose reference cannot.
Ambiguous selectors and unresolved configured `resolution_groups` on selected sections
flag the output for review, while still allowing source-backed records to be written.

New rows retain source identities and written values in a hidden provenance worksheet,
bound to the profile hash. Reordered source records and planner edits do not create duplicate
rows on rerun in update-existing mode. Empty-template mode instead produces a fresh
workbook each time. Corrupt metadata or a changed profile is rejected before writing.

This updater supports text-native PDFs and `.xlsx` templates without active formulas, tables,
merges, drawings or other structures needing a structure-aware row insertion implementation.
These inputs fail clearly. Outputs and reports cannot alias inputs. Input hashes are checked
again before publication, and a lock prevents simultaneous publication to the same workbook.
Reports are replaced individually; the workbook is published last as the completion marker.

To change a private profile, export it with `PrivateTransformationProfileService.export_profile`
and import the resulting document to verify its hash. Preserve generated metadata for repeat
runs with unchanged rules; review a baseline migration when changing those rules.
