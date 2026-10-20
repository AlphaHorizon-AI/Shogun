"""Master lifecycle tests isolate promotion from PDF parsing and workbook rules."""

import copy
import hashlib
import os
from pathlib import Path
from threading import Event

import pytest

from shogun.services import workbook_master


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def master_job(tmp_path, monkeypatch):
    template = tmp_path / "seed.xlsx"
    template.write_bytes(b"empty seed")
    pdf = tmp_path / "current.pdf"
    pdf.write_bytes(b"current source")
    profile_source = tmp_path / "rules.json"
    profile_source.write_bytes(b"profile")
    job = {
        "master_workbook_path": tmp_path / "Master" / "planning.xlsx",
        "template_workbook_path": template,
        "output_workbook_path": tmp_path / "Output" / "planning_v1.xlsx",
        "pdf_paths": [pdf],
        "profile_source_path": profile_source,
        "profile": {"parameters": {"workbook_update": {"mode": "maintain_master"}}},
    }
    calls = []
    result = {
        "comparison_report": {"status": "PASS", "review_required": False},
        "validation_summary": {
            "normalized_record_count": 2,
            "accounted_record_count": 2,
            "record_disposition_counts": {"INSERTED_RECORD_ROW": 2},
        },
        "report_paths": {},
    }

    def pipeline(**kwargs):
        calls.append(kwargs)
        output = Path(kwargs["output_workbook_path"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"generated: " + Path(kwargs["template_workbook_path"]).read_bytes())
        return {**copy.deepcopy(result), "output_sha256": digest(output)}

    monkeypatch.setattr(workbook_master, "run_sectioned_workbook_pipeline", pipeline)
    return job, calls, result, pipeline


def existing_master(job):
    master = job["master_workbook_path"]
    master.parent.mkdir(parents=True)
    master.write_bytes(b"master with planner details")
    return master


def test_initial_run_uses_seed_and_creates_separate_master(master_job):
    job, calls, _, _ = master_job
    result = workbook_master.run_workbook_master_pipeline(**job)
    master = job["master_workbook_path"]
    assert calls[0]["template_workbook_path"] == job["template_workbook_path"]
    assert calls[0]["expected_input_hashes"] == {
        path: digest(path)
        for path in [job["template_workbook_path"], *job["pdf_paths"], job["profile_source_path"]]
    }
    assert master.read_bytes() == job["output_workbook_path"].read_bytes()
    assert job["template_workbook_path"].read_bytes() == b"empty seed"
    assert result["master_lifecycle"] == {
        "master_workbook": str(master), "initialized": True, "promoted": True,
        "backup_workbook": None, "sha256": digest(master), "review_required": False,
    }
    assert not master.with_name(master.name + ".lock").exists()


def test_later_run_preserves_prior_master_in_retained_backup(master_job):
    job, calls, _, _ = master_job
    master = existing_master(job)
    before = master.read_bytes()
    result = workbook_master.run_workbook_master_pipeline(**job)
    assert calls[0]["template_workbook_path"] == master
    assert calls[0]["expected_input_hashes"][master] == hashlib.sha256(before).hexdigest()
    assert job["template_workbook_path"] not in calls[0]["expected_input_hashes"]
    backup = Path(result["master_lifecycle"]["backup_workbook"])
    assert backup.parent == master.parent
    assert backup.read_bytes() == before
    assert master.read_bytes() == b"generated: " + before
    assert result["master_lifecycle"]["initialized"] is False


def test_safe_review_result_can_maintain_master(master_job):
    job, _, result, _ = master_job
    result["comparison_report"]["review_required"] = True
    outcome = workbook_master.run_workbook_master_pipeline(**job)
    assert outcome["master_lifecycle"]["promoted"] is True
    assert outcome["master_lifecycle"]["review_required"] is True


@pytest.mark.parametrize("has_master", [False, True])
def test_pipeline_failure_never_replaces_master(master_job, monkeypatch, has_master):
    job, _, _, _ = master_job
    master = existing_master(job) if has_master else job["master_workbook_path"]
    before = master.read_bytes() if has_master else None

    def fail(**kwargs):
        raise ValueError("source validation failed")

    monkeypatch.setattr(workbook_master, "run_sectioned_workbook_pipeline", fail)
    with pytest.raises(ValueError, match="source validation failed"):
        workbook_master.run_workbook_master_pipeline(**job)
    assert (master.read_bytes() if master.exists() else None) == before
    assert not master.with_name(master.name + ".lock").exists()


@pytest.mark.parametrize("change,error", [
    ({"comparison_report": {"status": "FAIL"}}, "preservation validation failed"),
    ({"validation_summary": {}}, "accounting is incomplete"),
    ({"validation_summary": {"normalized_record_count": 2, "accounted_record_count": 1,
                              "record_disposition_counts": {"INSERTED_RECORD_ROW": 1}}}, "accounting is incomplete"),
    ({"validation_summary": {"normalized_record_count": 2, "accounted_record_count": 2,
                              "record_disposition_counts": {"INSERTED_RECORD_ROW": 1}}}, "accounting is incomplete"),
])
def test_failed_validation_never_promotes(master_job, change, error):
    job, _, result, _ = master_job
    master = existing_master(job)
    before = master.read_bytes()
    result.update(change)
    with pytest.raises(ValueError, match=error):
        workbook_master.run_workbook_master_pipeline(**job)
    assert master.read_bytes() == before


@pytest.mark.parametrize("changed", ["master", "pdf", "profile"])
def test_input_mutation_after_pipeline_prevents_promotion(master_job, monkeypatch, changed):
    job, _, _, pipeline = master_job
    master = existing_master(job)
    before = master.read_bytes()
    path = {"master": master, "pdf": job["pdf_paths"][0], "profile": job["profile_source_path"]}[changed]

    def mutate(**kwargs):
        result = pipeline(**kwargs)
        path.write_bytes(b"external edit")
        return result

    monkeypatch.setattr(workbook_master, "run_sectioned_workbook_pipeline", mutate)
    with pytest.raises(ValueError, match="inputs changed"):
        workbook_master.run_workbook_master_pipeline(**job)
    assert master.read_bytes() == (b"external edit" if changed == "master" else before)


def test_cancellation_after_output_does_not_promote(master_job, monkeypatch):
    job, _, _, pipeline = master_job
    master = existing_master(job)
    before = master.read_bytes()
    cancellation = Event()
    job["cancel_event"] = cancellation

    def cancel(**kwargs):
        result = pipeline(**kwargs)
        cancellation.set()
        return result

    monkeypatch.setattr(workbook_master, "run_sectioned_workbook_pipeline", cancel)
    with pytest.raises(RuntimeError, match="cancelled"):
        workbook_master.run_workbook_master_pipeline(**job)
    assert master.read_bytes() == before


def test_output_replaced_after_pipeline_validation_is_not_promoted(master_job, monkeypatch):
    job, _, _, pipeline = master_job
    master = existing_master(job)
    before = master.read_bytes()

    def replace_validated_output(**kwargs):
        result = pipeline(**kwargs)
        Path(kwargs["output_workbook_path"]).write_bytes(b"another writer's workbook")
        return result

    monkeypatch.setattr(workbook_master, "run_sectioned_workbook_pipeline", replace_validated_output)
    with pytest.raises(ValueError, match="generated workbook changed"):
        workbook_master.run_workbook_master_pipeline(**job)
    assert master.read_bytes() == before
    assert list(master.parent.glob("planning_previous_v*.xlsx")) == []
    assert list(master.parent.glob(".shogun-master-*")) == []


@pytest.mark.parametrize("invalid_hash", [None, "invalid", "A" * 64, True])
def test_missing_or_invalid_validated_output_hash_prevents_promotion(master_job, monkeypatch, invalid_hash):
    job, _, _, pipeline = master_job
    master = existing_master(job)
    before = master.read_bytes()

    def invalid_digest(**kwargs):
        return {**pipeline(**kwargs), "output_sha256": invalid_hash}

    monkeypatch.setattr(workbook_master, "run_sectioned_workbook_pipeline", invalid_digest)
    with pytest.raises(ValueError, match="validated output hash is missing or invalid"):
        workbook_master.run_workbook_master_pipeline(**job)
    assert master.read_bytes() == before


def test_promotion_failure_keeps_master_and_backup(master_job, monkeypatch):
    job, _, _, _ = master_job
    master = existing_master(job)
    before = master.read_bytes()

    def fail_replace(source, target):
        raise PermissionError("master open in Excel")

    monkeypatch.setattr(workbook_master.os, "replace", fail_replace)
    with pytest.raises(PermissionError, match="open in Excel"):
        workbook_master.run_workbook_master_pipeline(**job)
    assert master.read_bytes() == before
    assert [path.read_bytes() for path in master.parent.glob("planning_previous_v*.xlsx")] == [before]
    assert list(master.parent.glob(".shogun-master-*")) == []
    assert not master.with_name(master.name + ".lock").exists()


def test_master_lock_covers_runs_with_different_outputs(master_job, monkeypatch):
    job, _, _, pipeline = master_job
    second = {**job, "output_workbook_path": job["output_workbook_path"].with_name("second.xlsx")}

    def concurrent(**kwargs):
        with pytest.raises(ValueError, match="master is already being processed"):
            workbook_master.run_workbook_master_pipeline(**second)
        return pipeline(**kwargs)

    monkeypatch.setattr(workbook_master, "run_sectioned_workbook_pipeline", concurrent)
    workbook_master.run_workbook_master_pipeline(**job)
    assert not second["output_workbook_path"].exists()


def test_master_created_by_another_writer_is_not_replaced(master_job, monkeypatch):
    job, _, _, pipeline = master_job

    def concurrent(**kwargs):
        result = pipeline(**kwargs)
        job["master_workbook_path"].write_bytes(b"other writer")
        return result

    monkeypatch.setattr(workbook_master, "run_sectioned_workbook_pipeline", concurrent)
    with pytest.raises(ValueError, match="appeared during processing"):
        workbook_master.run_workbook_master_pipeline(**job)
    assert job["master_workbook_path"].read_bytes() == b"other writer"


@pytest.mark.parametrize("kind", ["seed", "output", "report", "pdf_hardlink"])
def test_master_cannot_alias_any_input_or_output(master_job, kind):
    job, calls, _, _ = master_job
    if kind == "seed":
        job["master_workbook_path"] = job["template_workbook_path"]
    elif kind == "output":
        job["master_workbook_path"] = job["output_workbook_path"]
    else:
        master = existing_master(job)
        if kind == "report":
            report = job["output_workbook_path"].with_name("planning_v1_audit_report.json")
            report.parent.mkdir(parents=True)
            os.link(master, report)
        else:
            job["pdf_paths"][0].unlink()
            os.link(master, job["pdf_paths"][0])
    with pytest.raises(ValueError, match="master must be separate"):
        workbook_master.run_workbook_master_pipeline(**job)
    assert calls == []


def test_reference_workbook_is_never_a_master_input(master_job):
    job, calls, _, _ = master_job
    job["reference_workbook_path"] = job["template_workbook_path"]
    with pytest.raises(ValueError, match="Reference workbooks cannot be inputs"):
        workbook_master.run_workbook_master_pipeline(**job)
    assert calls == []


@pytest.mark.parametrize("profile", [None, {}, {"parameters": []},
    {"parameters": {"workbook_update": {"mode": "populate_template"}}}])
def test_wrong_profile_mode_fails_before_creating_master_directory(master_job, profile):
    job, calls, _, _ = master_job
    job["profile"] = profile
    with pytest.raises(ValueError, match="maintain_master profile"):
        workbook_master.run_workbook_master_pipeline(**job)
    assert not job["master_workbook_path"].parent.exists()
    assert calls == []


def test_expected_hashes_accept_absolute_string_keys_and_include_master(master_job):
    job, calls, _, _ = master_job
    master = existing_master(job)
    job["expected_input_hashes"] = {
        str(path): digest(path) for path in [master, *job["pdf_paths"], job["profile_source_path"]]
    }
    workbook_master.run_workbook_master_pipeline(**job)
    assert master in calls[0]["expected_input_hashes"]


def test_stale_prepared_inputs_fail_without_running_pipeline(master_job):
    job, calls, _, _ = master_job
    master = existing_master(job)
    before = master.read_bytes()
    job["expected_input_hashes"] = {
        path: digest(path)
        for path in [job["template_workbook_path"], *job["pdf_paths"], job["profile_source_path"]]
    }
    with pytest.raises(ValueError, match="changed after job preparation"):
        workbook_master.run_workbook_master_pipeline(**job)
    assert calls == []
    assert master.read_bytes() == before
