"""Textual Gradient Generator — structured natural-language feedback.

Produces structured JSON feedback from failed or weak candidates (§14.6).
The gradient captures the failure summary, root causes, recommended changes,
and constraints to preserve, enabling the candidate updater to produce an
improved version.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def generate_gradient(
    evaluation_result: dict[str, Any],
    execution_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate a textual gradient from an evaluation result.

    The gradient structure follows the build paper §14.6 example::

        {
            "failure_summary": "...",
            "root_causes": ["..."],
            "recommended_changes": [
                {"operation": "modify_rule", "instruction": "..."}
            ],
            "constraints_to_preserve": ["..."],
            "dimension_feedback": {...}
        }
    """
    gradient: dict[str, Any] = {
        "failure_summary": "",
        "root_causes": [],
        "recommended_changes": [],
        "constraints_to_preserve": [],
        "dimension_feedback": {},
    }

    # Hard failures produce the most specific gradients
    hard_failures = evaluation_result.get("hard_failures", [])
    if hard_failures:
        gradient["failure_summary"] = f"Candidate failed with {len(hard_failures)} hard failure(s): " + "; ".join(
            f["type"] for f in hard_failures
        )
        gradient["root_causes"] = [f.get("description", f["type"]) for f in hard_failures]
        gradient["recommended_changes"] = [
            {
                "operation": "fix_hard_failure",
                "instruction": f"Resolve hard failure: {f['type']}. {f.get('description', '')}",
            }
            for f in hard_failures
        ]
        return gradient

    # Dimension-level feedback for weak scores
    dimension_scores = evaluation_result.get("dimension_scores", {})
    weak_dimensions = [(dim, score) for dim, score in dimension_scores.items() if score < 0.7]

    if not weak_dimensions:
        gradient["failure_summary"] = "No significant weaknesses detected."
        return gradient

    gradient["failure_summary"] = f"Candidate has {len(weak_dimensions)} weak dimension(s): " + ", ".join(
        f"{d} ({s:.0%})" for d, s in weak_dimensions
    )

    for dim, score in weak_dimensions:
        feedback = _dimension_feedback(dim, score, execution_context)
        gradient["dimension_feedback"][dim] = feedback
        if feedback.get("root_cause"):
            gradient["root_causes"].append(feedback["root_cause"])
        if feedback.get("recommendation"):
            gradient["recommended_changes"].append(
                {
                    "operation": "improve_dimension",
                    "dimension": dim,
                    "instruction": feedback["recommendation"],
                }
            )

    # Constraints that must be preserved regardless of changes
    gradient["constraints_to_preserve"] = [
        "Do not modify existing active skill version directly.",
        "Preserve all planner-adjusted fields.",
        "Maintain ToolGate policy compliance.",
    ]

    return gradient


def _dimension_feedback(
    dimension: str,
    score: float,
    context: dict[str, Any] | None,
) -> dict[str, str]:
    """Generate feedback for a specific weak dimension."""

    templates = {
        "task_success": {
            "root_cause": "The candidate did not complete the task successfully.",
            "recommendation": "Ensure the tool chain reaches a terminal state with valid output.",
        },
        "correctness": {
            "root_cause": "Output does not match the expected result.",
            "recommendation": "Verify output values against the expected schema and reference data.",
        },
        "policy_compliance": {
            "root_cause": "One or more policy checks were violated.",
            "recommendation": "Review ToolGate policy constraints and ensure all tool calls comply.",
        },
        "tool_efficiency": {
            "root_cause": "Too many tool calls were used to complete the task.",
            "recommendation": "Reduce redundant tool invocations; combine operations where safe.",
        },
        "robustness": {
            "root_cause": "Edge cases were not handled correctly.",
            "recommendation": "Add handling for missing data, unexpected formats, and boundary conditions.",
        },
        "latency": {
            "root_cause": "Execution took longer than the target latency.",
            "recommendation": "Optimize the tool chain to reduce unnecessary sequential calls.",
        },
        "cost": {
            "root_cause": "Execution cost exceeded the target budget.",
            "recommendation": "Use cheaper model tiers for sub-tasks that do not require high capability.",
        },
    }

    template = templates.get(
        dimension,
        {
            "root_cause": f"Dimension '{dimension}' scored below threshold ({score:.0%}).",
            "recommendation": f"Investigate and improve the '{dimension}' dimension.",
        },
    )

    return {
        "dimension": dimension,
        "score": f"{score:.0%}",
        **template,
    }
