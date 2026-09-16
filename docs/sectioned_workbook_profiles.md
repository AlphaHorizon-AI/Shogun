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
configured PDFs directly. Do not attach a `workbook_update` profile to a Samurai
extraction node: its row-matrix path does not implement workbook preservation or
the page-aware parser. Such profiles now receive a setup error rather than an
empty-number error or a model fallback. Existing document-extraction profiles
continue to use the Samurai path.

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

Keep workflow policy explicit:

- `source_identity_fields` identifies a source record independently of PDF page/order.
- Reference matching preserves leading zeros unless `match_strip_leading_zeros` is true.
- Existing quantity/date cells are filled only when blank. Nonblank values, including zero,
  remain under planner control.
- A section rule's `policy` defaults to `fill_blank`; `replace` explicitly permits replacement.
- `alternative_quantity_spec` holds disagreement for review instead of choosing a value.
- `require_date_in_planning_horizon` filters against configured month headers.
  `planning_month_quantity` additionally writes the quantity into that month's cell.
- `when` uses the existing section conditions, for example
  `{"field": "zone", "operator": "equals", "value": "A"}`.

The engine preserves baseline cells and formatting, rejects ambiguous record placement,
and retains one disposition per source record. Reports include normalized source records,
the audit, permitted changes, and a preservation comparison. A reference workbook with a
compatible layout can supply row comparison metrics; a prose reference cannot.

New rows retain source identities and written values in a hidden provenance worksheet,
bound to the profile hash. Reordered source records and planner edits do not create duplicate
rows on rerun. Corrupt metadata or a changed profile is rejected before writing.

This updater supports text-native PDFs and `.xlsx` templates without active formulas, tables,
merges, drawings or other structures needing a structure-aware row insertion implementation.
These inputs fail clearly. Outputs and reports cannot alias inputs. Input hashes are checked
again before publication, and a lock prevents simultaneous publication to the same workbook.
Reports are replaced individually; the workbook is published last as the completion marker.

To change a private profile, export it with `PrivateTransformationProfileService.export_profile`
and import the resulting document to verify its hash. Preserve generated metadata for repeat
runs with unchanged rules; review a baseline migration when changing those rules.
