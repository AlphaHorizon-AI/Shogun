from __future__ import annotations

import json
from pathlib import Path

import tomllib

TEMPLATE_IDS = {
    "ops-brief-channel-broadcast": "intermediate",
    "incident-triage-channel-alert": "intermediate",
    "adv-intelligence-channel-command": "advanced",
}


def _catalog() -> dict:
    path = Path(__file__).parents[1] / "shogun" / "resources" / "flow_templates.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_template_catalog_is_included_in_installed_package_data():
    pyproject = tomllib.loads(
        (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert "resources/*.json" in pyproject["tool"]["setuptools"]["package-data"]["shogun"]


def test_channel_templates_are_catalogued_and_connected():
    catalog = _catalog()
    templates = {template["id"]: template for template in catalog["templates"]}

    assert catalog["total_templates"] == len(catalog["templates"])
    for category in catalog["categories"]:
        assert category["count"] == len(category["templates"])

    for template_id, difficulty in TEMPLATE_IDS.items():
        template = templates[template_id]
        assert template["difficulty"] == difficulty
        assert template["node_count"] == len(template["nodes"])

        nodes = {node["id"]: node for node in template["nodes"]}
        assert any(node["node_type"] == "channel_send" for node in nodes.values())
        assert all(edge["source_node_id"] in nodes for edge in template["edges"])
        assert all(edge["target_node_id"] in nodes for edge in template["edges"])


def test_advanced_channel_template_has_parallel_analysis_and_approval():
    template = next(
        item for item in _catalog()["templates"]
        if item["id"] == "adv-intelligence-channel-command"
    )
    types = [node["node_type"] for node in template["nodes"]]

    assert types.count("samurai") == 3
    assert "shogun_approval" in types
    assert "channel_send" in types


def test_daily_business_news_template_runs_at_eight_and_uses_three_sources():
    template = next(
        item for item in _catalog()["templates"]
        if item["id"] == "ops-brief-channel-broadcast"
    )
    nodes = template["nodes"]

    assert template["name"] == "Daily Business News Brief to Telegram"
    assert template["trigger_type"] == "scheduled"
    assert template["schedule_config"] == {
        "frequency": "nightly",
        "schedule_time": "08:00",
    }

    scheduled_input = next(node for node in nodes if node["node_type"] == "input")
    assert scheduled_input["config"]["input_type"] == "scheduled"
    assert scheduled_input["config"]["schedule_time"] == "08:00"

    websites = {
        node["config"]["url"]
        for node in nodes
        if node["node_type"] == "mado_browser" and node["config"]["action"] == "navigate"
    }
    assert websites == {
        "https://www.reuters.com/business/",
        "https://apnews.com/hub/business",
        "https://www.bbc.com/business",
    }

    channel_node = next(node for node in nodes if node["node_type"] == "channel_send")
    assert channel_node["config"]["channel"] == "telegram"
