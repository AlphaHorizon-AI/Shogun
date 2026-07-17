from shogun.services.native_skills import NATIVE_TOOLS
from shogun.services.posture_guard import filter_tools_by_posture


def _workflow_tools():
    return [
        tool for tool in NATIVE_TOOLS
        if tool["function"]["name"] in {
            "create_agent_flow", "edit_agent_flow",
            "create_flow_stack", "edit_flow_stack",
        }
    ]


def test_workflow_creation_tools_exist_and_activation_is_explicit():
    tools = {tool["function"]["name"]: tool for tool in _workflow_tools()}

    assert set(tools) == {
        "create_agent_flow", "edit_agent_flow",
        "create_flow_stack", "edit_flow_stack",
    }
    for tool in tools.values():
        parameters = tool["function"]["parameters"]
        assert parameters["properties"]["activate"]["type"] == "boolean"
        assert "activate" not in parameters["required"]


def test_workflow_tools_are_blocked_below_tactical_posture():
    allowed, denied = filter_tools_by_posture(
        _workflow_tools(),
        {"agentflow_create": False, "flowstack_create": False},
    )

    assert allowed == []
    assert set(denied) == {
        "create_agent_flow", "edit_agent_flow",
        "create_flow_stack", "edit_flow_stack",
    }


def test_workflow_tools_are_posture_eligible_at_tactical_and_above():
    allowed, denied = filter_tools_by_posture(
        _workflow_tools(),
        {"agentflow_create": True, "flowstack_create": True},
    )

    assert {tool["function"]["name"] for tool in allowed} == {
        "create_agent_flow", "edit_agent_flow",
        "create_flow_stack", "edit_flow_stack",
    }
    assert denied == []
