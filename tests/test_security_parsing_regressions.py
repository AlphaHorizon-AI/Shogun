from shogun.mapping.engine import _json_from_text
from shogun.services.enterprise_transformations import _parse_payload


def test_enterprise_payload_accepts_fenced_json_without_regex_backtracking():
    assert _parse_payload('```json\n{"records": [{"id": 1}]}\n```') == {
        "records": [{"id": 1}],
    }


def test_mapping_text_finds_fenced_json_without_regex_backtracking():
    assert _json_from_text('Model preface\n```JSON\n[{"id": 7}]\n```\nModel suffix') == [
        {"id": 7},
    ]
