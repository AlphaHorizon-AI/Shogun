"""Tests for Yellow Label SkillOpt Lab implementation.

Verifies:
1. Product-capability guards and edition boundaries
2. Gensui guard endpoints return 403 CAPABILITY_UNAVAILABLE
3. BushidoEngine operational cadence preset for SkillOpt Regression Sweep
4. Evaluator weighted scoring and hard-failure rules (§38)
5. Textual gradient generator structured output (§14.6)
"""

import pytest

from shogun.edition import REMOVED_FEATURES
from shogun.services.bushido_engine import PRESET_SCHEDULES
from shogun.services.capability_service import CapabilityService, CapabilityUnavailable
from shogun.services.skillopt.lab.evaluator import (
    HARD_FAILURE_TYPES,
    WEIGHT_DISTRIBUTION,
    compute_weighted_score,
    detect_hard_failures,
)
from shogun.services.skillopt.lab.gradient_generator import generate_gradient


def test_edition_boundary_removes_gensui_features():
    """Gensui sub-features must be explicitly in REMOVED_FEATURES for Yellow Label."""
    assert "gensui" in REMOVED_FEATURES
    assert "gensui_skill_publication" in REMOVED_FEATURES
    assert "gensui_skill_distribution" in REMOVED_FEATURES
    assert "gensui_competence_registry" in REMOVED_FEATURES
    assert "enterprise_skill_sync" in REMOVED_FEATURES


def test_capability_service_guards():
    """CapabilityService must allow local SkillOpt features and deny Gensui features."""
    caps = CapabilityService.get()

    # Local capabilities allowed
    assert caps.enabled("skillopt.lab") is True
    assert caps.enabled("skillopt.regression") is True
    assert caps.enabled("skillopt.local_versions") is True
    assert caps.enabled("skillopt.local_benchmark") is True

    # Enterprise capabilities blocked
    assert caps.enabled("gensui.skills.publish") is False
    assert caps.enabled("gensui.skills.distribute") is False
    assert caps.enabled("gensui.competence") is False

    # Require raises CapabilityUnavailable for Gensui
    with pytest.raises(CapabilityUnavailable):
        caps.require("gensui.skills.publish")


def test_bushido_operational_cadence_preset():
    """Bushido PRESET_SCHEDULES must include the 5th preset: SkillOpt Regression Sweep."""
    preset_names = [p["name"] for p in PRESET_SCHEDULES]
    preset_job_types = [p["job_type"] for p in PRESET_SCHEDULES]

    assert "SkillOpt Regression Sweep" in preset_names
    assert "skillopt_regression_sweep" in preset_job_types

    skillopt_preset = next(p for p in PRESET_SCHEDULES if p["job_type"] == "skillopt_regression_sweep")
    assert skillopt_preset["frequency"] == "weekly"
    assert skillopt_preset["schedule_time"] == "03:30"
    assert "wed" in skillopt_preset["schedule_days"]
    assert skillopt_preset["is_preset"] is True
    assert skillopt_preset["is_enabled"] is False


def test_evaluator_weighted_scoring():
    """Evaluator weighted scoring follows §38 breakdown."""
    dimensions = {
        "task_success": 1.0,
        "correctness": 1.0,
        "policy_compliance": 1.0,
        "tool_efficiency": 1.0,
        "robustness": 1.0,
        "latency": 1.0,
        "cost": 1.0,
    }
    score = compute_weighted_score(dimensions)
    assert pytest.approx(score, 0.001) == 1.0

    # Test weight calculation with partial scores
    zero_dimensions = {k: 0.0 for k in dimensions}
    assert compute_weighted_score(zero_dimensions) == 0.0

    # Test sum of weights equals 1.0
    assert pytest.approx(sum(WEIGHT_DISTRIBUTION.values()), 0.001) == 1.0


def test_evaluator_hard_failure_detection():
    """Hard failure detection identifies §38 critical failure types."""
    assert "wrong_article_updated" in HARD_FAILURE_TYPES
    assert "security_violation" in HARD_FAILURE_TYPES

    clean_exec = {"failures": []}
    assert len(detect_hard_failures(clean_exec)) == 0

    bad_exec = {"failures": ["wrong_article_updated", "unauthorized_write"]}
    detected = detect_hard_failures(bad_exec)
    assert len(detected) == 2


def test_textual_gradient_generator():
    """Textual gradient generator produces structured diagnostic feedback."""
    eval_result = {
        "hard_failures": [{"type": "wrong_article_updated", "description": "Updated article #999 instead of #123"}],
        "dimension_scores": {"task_success": 0.0, "correctness": 0.2},
    }

    gradient = generate_gradient(evaluation_result=eval_result)

    assert "failure_summary" in gradient
    assert "root_causes" in gradient
    assert "recommended_changes" in gradient
    assert len(gradient["root_causes"]) > 0
    assert "wrong_article_updated" in gradient["failure_summary"]
