"""SkillOpt Lab Evaluator — weighted scoring and hard-failure detection.

Implements the evaluation strategy from §14.5 and §38 of the build paper.
Prefers deterministic evaluation; LLM evaluation is used only when needed.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Evaluation weight distribution (§38)
WEIGHT_DISTRIBUTION = {
    "task_success": 0.35,
    "correctness": 0.25,
    "policy_compliance": 0.15,
    "tool_efficiency": 0.10,
    "robustness": 0.07,
    "latency": 0.05,
    "cost": 0.03,
}

# Hard failure conditions — any of these means the candidate cannot be
# validated regardless of aggregate score (§38)
HARD_FAILURE_TYPES = frozenset(
    {
        "wrong_article_updated",
        "unauthorized_write",
        "original_file_overwritten",
        "planner_field_destroyed",
        "policy_bypass",
        "data_loss",
        "security_violation",
    }
)


def compute_weighted_score(dimension_scores: dict[str, float]) -> float:
    """Compute a weighted aggregate score from individual dimension scores.

    Each dimension score should be between 0.0 and 1.0. Missing dimensions
    are treated as 0.0.
    """
    total = 0.0
    for dimension, weight in WEIGHT_DISTRIBUTION.items():
        score = dimension_scores.get(dimension, 0.0)
        total += score * weight
    return round(total, 4)


def detect_hard_failures(
    execution_result: dict[str, Any],
) -> list[dict[str, str]]:
    """Check execution results for hard failure conditions.

    Returns a list of detected hard failures. An empty list means the
    candidate passes the hard-failure check.
    """
    failures = []
    for failure_type in execution_result.get("failures", []):
        if isinstance(failure_type, dict):
            ftype = failure_type.get("type", "")
            desc = failure_type.get("description", "")
            ev = failure_type.get("evidence", "")
        else:
            ftype = str(failure_type)
            desc = ""
            ev = ""
        if ftype in HARD_FAILURE_TYPES:
            failures.append(
                {
                    "type": ftype,
                    "description": desc,
                    "evidence": ev,
                }
            )
    return failures


def evaluate_candidate(
    execution_result: dict[str, Any],
    expected_output: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate a candidate execution result.

    Follows the preferred evaluation order (§14.5):
    1. Deterministic checks
    2. Schema / invariant validation
    3. Reference-output comparison
    4. LLM evaluator (only where needed)

    Returns an evaluation result dict with score, hard failures, and
    per-dimension scores.
    """
    # 1. Check for hard failures first
    hard_failures = detect_hard_failures(execution_result)
    if hard_failures:
        return {
            "passed": False,
            "score": 0.0,
            "hard_failures": hard_failures,
            "dimension_scores": {},
            "evaluation_method": "deterministic",
        }

    # 2. Compute dimension scores from execution metrics
    dimension_scores = _extract_dimension_scores(execution_result, expected_output)

    # 3. Compute weighted aggregate
    aggregate_score = compute_weighted_score(dimension_scores)

    return {
        "passed": aggregate_score >= 0.5,
        "score": aggregate_score,
        "hard_failures": [],
        "dimension_scores": dimension_scores,
        "evaluation_method": "deterministic",
    }


def _extract_dimension_scores(
    execution_result: dict[str, Any],
    expected_output: dict[str, Any] | None,
) -> dict[str, float]:
    """Extract per-dimension scores from execution metrics.

    Uses deterministic checks where possible. Falls back to heuristic
    scoring for dimensions that require model-based evaluation.
    """
    scores: dict[str, float] = {}

    # Task success — did the execution complete without errors?
    scores["task_success"] = 1.0 if execution_result.get("status") == "completed" else 0.0

    # Correctness — compare against expected output if available
    if expected_output:
        actual = execution_result.get("output", {})
        matches = sum(1 for k, v in expected_output.items() if actual.get(k) == v)
        total = len(expected_output) or 1
        scores["correctness"] = matches / total
    else:
        scores["correctness"] = scores["task_success"]

    # Policy compliance — were all policy checks passed?
    policy_violations = execution_result.get("policy_violations", 0)
    scores["policy_compliance"] = 1.0 if policy_violations == 0 else 0.0

    # Tool efficiency — fewer tool calls is better
    tool_calls = execution_result.get("tool_call_count", 5)
    scores["tool_efficiency"] = max(0.0, 1.0 - (tool_calls / 20.0))

    # Robustness — did it handle edge cases?
    scores["robustness"] = 1.0 if not execution_result.get("edge_case_failures") else 0.5

    # Latency — normalized against a 10-second target
    latency = execution_result.get("latency_seconds", 5.0)
    scores["latency"] = max(0.0, 1.0 - (latency / 10.0))

    # Cost — normalized against a €1 target
    cost = execution_result.get("cost_eur", 0.1)
    scores["cost"] = max(0.0, 1.0 - (cost / 1.0))

    return scores
