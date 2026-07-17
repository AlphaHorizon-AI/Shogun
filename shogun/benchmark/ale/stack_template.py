"""Canonical Stack Orchestrator plan for ALE tasks."""

ALE_TASK_RUNNER_STACK = [
    "Parse Task",
    "Inspect Sandbox",
    "Identify Required Applications and Files",
    "Create Work Plan",
    "Execute Work Plan",
    "Observe Result",
    "Self-Verify Against Task Instruction",
    "Retry or Repair if Needed",
    "Package Output Artifacts",
    "Produce Final Answer",
    "Export Trajectory",
]


def as_stack_plan() -> list[dict]:
    return [
        {
            "name": name,
            "step_type": "benchmark",
            "expected_output": f"ALE benchmark phase completed: {name}",
            "risk_level": "medium" if index in {5, 8} else "low",
            "required_tools": ["cua", "sandbox"] if 2 <= index <= 8 else [],
            "model_hint": "ale_balanced",
        }
        for index, name in enumerate(ALE_TASK_RUNNER_STACK, start=1)
    ]
