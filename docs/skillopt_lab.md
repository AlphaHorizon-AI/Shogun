# SkillOpt Lab preview

Yellow Label 1.47.106 adds the SkillOpt Lab interface, local skill version
management, regression suite definitions, and storage for future evaluation
evidence. This is a preview: automated Lab optimization, regression execution,
and model benchmarking are not implemented in this release. Execution requests
must report that they are unavailable and must not produce simulated pass rates
or model competence results. Existing runtime SkillOpt remains available.

Local changes remain on this Shogun installation. Enterprise publication and
distribution are unavailable. The added denial endpoints do not enable those
capabilities.

Startup applies the additive SkillOpt Lab database migration automatically.
It preserves existing skill versions and candidates while adding local scope,
quarantine, approval, and tool schema metadata. Back up the database before an
upgrade using the normal Shogun backup process.

Workflow-specific transformation rules belong in private profile files. The
generic PDF-to-Excel engine and its configuration are documented in
[Private profiles for sectioned workbook updates](sectioned_workbook_profiles.md).
Customer PDFs, workbooks, profiles, and generated evidence are not distributed
with this release.
