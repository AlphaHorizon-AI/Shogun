"""Deterministic Mapping / RPA engine and AgentFlow handoff tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from openpyxl import Workbook, load_workbook
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shogun.api.deps import get_db
from shogun.config import settings
from shogun.db.base import Base
from shogun.db.models.mapping_template import MappingTemplate
from shogun.engine.flow_engine import (
    _exec_mapping_rpa,
    _exec_office,
    _mapping_payload_from_predecessors,
    _write_openpyxl_mapping,
)
from shogun.mapping.engine import execute_mapping
from shogun.mapping.errors import MappingFieldMissing, MappingSchemaError, MappingTypeError
from shogun.mapping.schema import MappingConfig
from shogun.schemas.agent_flow import AgentFlowNodeCreate


def _config(**overrides):
    config = {
        "version": 1,
        "name": "Supplier PDF to Excel",
        "mode": "strict",
        "output": {"type": "table", "start_cell": "A1"},
        "mappings": [
            {"source": "article_number", "target": "A", "type": "string", "required": True, "transform": ["trim"]},
            {"source": "description", "target": "B", "type": "string", "required": True},
            {"source": "quantity", "target": "C", "type": "integer", "required": True, "transform": ["convert"]},
            {"source": "unit_price", "target": "D", "type": "decimal", "transform": ["decimal_normalize"]},
            {"source": "currency", "target": "E", "type": "string", "default": "EUR", "transform": ["uppercase"]},
        ],
    }
    config.update(overrides)
    return config


def test_canonical_pdf_to_excel_mapping_is_typed_and_ordered():
    result = execute_mapping(
        {
            "article_number": " 68947124 ",
            "description": "Pump Housing",
            "quantity": "4",
            "unit_price": "129,95",
            "currency": "eur",
        },
        _config(),
    )

    assert result["status"] == "SUCCESS"
    assert result["rows"] == [["68947124", "Pump Housing", 4, 129.95, "EUR"]]
    assert result["records_written"] == 1


def test_array_mapping_nested_path_and_lineage():
    config = _config(
        input_path="items",
        output={"type": "range", "start_cell": "A12", "sheet": "Products"},
    )
    result = execute_mapping(
        {
            "items": [
                {"article_number": "A1", "description": "Pump", "quantity": "2", "unit_price": "10", "source_page": 4},
                {
                    "article_number": "A2",
                    "description": "Valve",
                    "quantity": "5",
                    "unit_price": "4,50",
                    "source_page": 5,
                },
            ]
        },
        config,
    )

    assert result["rows"] == [["A1", "Pump", 2, 10, "EUR"], ["A2", "Valve", 5, 4.5, "EUR"]]
    assert result["start_cell"] == "A12"
    assert result["sheet"] == "Products"
    assert [item["page"] for item in result["lineage"]] == [4, 5]


def test_aliases_are_explicit_and_deterministic():
    result = execute_mapping(
        {"Artikel-Nr": "68947124", "description": "Pump", "quantity": 4, "unit_price": 1},
        _config(aliases={"article_number": ["Artikel-Nr", "SKU"]}),
    )
    assert result["rows"][0][0] == "68947124"


def test_missing_required_field_fails_before_output():
    with pytest.raises(MappingFieldMissing) as error:
        execute_mapping({"description": "Pump", "quantity": 4, "unit_price": 1}, _config())
    assert error.value.code == "VALIDATION_FAILED"
    assert error.value.field == "article_number"


def test_strict_mode_rejects_unknown_fields():
    payload = {
        "article_number": "A1",
        "description": "Pump",
        "quantity": 1,
        "unit_price": 2,
        "unexpected": "do not silently discard",
    }
    with pytest.raises(MappingSchemaError, match="Unknown fields"):
        execute_mapping(payload, _config())


def test_lenient_mode_converts_values_but_strict_requires_explicit_conversion():
    config = {
        "mode": "strict",
        "output": {"type": "table"},
        "mappings": [{"source": "quantity", "target": "A", "type": "integer", "required": True}],
    }
    with pytest.raises(MappingTypeError):
        execute_mapping({"quantity": "5"}, config)
    config["mode"] = "lenient"
    assert execute_mapping({"quantity": "5"}, config)["rows"] == [[5]]


def test_serialized_optional_rule_does_not_gain_an_implicit_default():
    config = MappingConfig.model_validate(
        {
            "mode": "lenient",
            "output": {"type": "table"},
            "mappings": [{"source": "quantity", "target": "A", "type": "integer"}],
        }
    )
    restored = MappingConfig.model_validate(config.model_dump(mode="json"))
    assert restored.mappings[0].has_default is False


def test_cell_mapping_and_openpyxl_handoff_preserve_types():
    config = {
        "mode": "lenient",
        "output": {"type": "cells", "sheet": "Invoice"},
        "mappings": [
            {"source": "customer", "target": "B4", "type": "string", "required": True},
            {"source": "quantity", "target": "E3", "type": "integer", "required": True},
        ],
    }
    result = execute_mapping({"customer": "Customer A", "quantity": "4"}, config)
    assert result["cells"] == {"B4": "Customer A", "E3": 4}

    workbook = Workbook()
    sheet = workbook.active
    _write_openpyxl_mapping(sheet, result)
    assert sheet["B4"].value == "Customer A"
    assert sheet["E3"].value == 4


def test_safe_formula_and_duplicate_replace():
    config = {
        "mode": "lenient",
        "duplicate_key": "sku",
        "duplicate_policy": "replace",
        "output": {"type": "table"},
        "mappings": [
            {"source": "sku", "target": "A", "type": "string", "required": True},
            {"source": "quantity", "target": "B", "type": "integer", "required": True},
            {"source": "unit_price", "target": "C", "type": "decimal", "required": True},
            {"expression": "quantity * unit_price", "target": "D", "type": "decimal"},
        ],
    }
    result = execute_mapping(
        [
            {"sku": "A1", "quantity": 1, "unit_price": 10},
            {"sku": "A1", "quantity": 2, "unit_price": 10},
        ],
        config,
    )
    assert result["rows"] == [["A1", 2, 10, 20]]


def test_record_skip_produces_partial_without_corrupting_valid_rows():
    config = {
        "mode": "lenient",
        "on_record_error": "skip",
        "output": {"type": "table"},
        "mappings": [{"source": "quantity", "target": "A", "type": "integer", "required": True}],
    }
    result = execute_mapping([{"quantity": "5"}, {"quantity": "four"}], config)
    assert result["status"] == "PARTIAL"
    assert result["rows"] == [[5]]
    assert result["records_failed"] == 1


def test_office_handoff_rejects_validation_failed_payload():
    with pytest.raises(ValueError, match="not writable"):
        _mapping_payload_from_predecessors(
            {
                "mapping": {
                    "__shogun_mapping_output__": True,
                    "status": "VALIDATION_FAILED",
                    "errors": [{"message": "article_number is missing"}],
                }
            }
        )


@pytest.mark.anyio
async def test_agentflow_executor_routes_structured_mapping_failures():
    result = await _exec_mapping_rpa(
        _config(),
        {"samurai": {"description": "Pump"}},
        flow_id="flow-1",
        node_id="mapping-1",
    )
    assert result["status"] == "VALIDATION_FAILED"
    assert result["errors"][0]["field"] == "article_number"


def test_agentflow_node_schema_normalizes_mapping_configuration():
    node = AgentFlowNodeCreate(node_type="mapping_rpa", label="Map", config=_config())
    assert node.config["mappings"][4]["has_default"] is True
    assert node.config["output"]["type"] == "table"


@pytest.mark.anyio
async def test_canonical_mapping_to_excel_file_end_to_end(tmp_path, monkeypatch):
    mapped = execute_mapping(
        {
            "article_number": "68947124",
            "description": "Pump Housing",
            "quantity": "4",
            "unit_price": "129,95",
        },
        _config(output={"type": "range", "start_cell": "A2", "sheet": "Products"}),
    )
    monkeypatch.setattr(settings, "workspace_path", tmp_path)
    monkeypatch.setattr("shogun.office.config.load_office_config", lambda: SimpleNamespace(enabled=True))

    result = await _exec_office(
        {
            "action": "excel_create",
            "output_path": "Output",
            "output_filename": "canonical.xlsx",
            "sheet_name": "Products",
        },
        "ignored textual context",
        predecessor_outputs={"mapping": mapped},
    )

    assert "canonical.xlsx" in result
    workbook = load_workbook(tmp_path / "Output" / "canonical.xlsx", data_only=True)
    try:
        sheet = workbook["Products"]
        assert [sheet.cell(2, column).value for column in range(1, 6)] == [
            "68947124",
            "Pump Housing",
            4,
            129.95,
            "EUR",
        ]
    finally:
        workbook.close()


@pytest.mark.anyio
async def test_preview_endpoint_returns_structured_validation_failure(client):
    response = await client.post(
        "/api/v1/mapping-rpa/preview",
        json={"config": _config(), "input": {"description": "Pump"}},
        headers={"X-Shogun-Infrastructure-Token": str(settings.infrastructure_admin_token or "")},
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "VALIDATION_FAILED"
    assert body["errors"][0]["field"] == "article_number"


@pytest.mark.anyio
async def test_mapping_template_crud_is_versioned_and_soft_deleted(api_app, client, tmp_path):
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'mapping-templates.db').as_posix()}"
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: Base.metadata.create_all(
                sync_connection,
                tables=[MappingTemplate.__table__],
            )
        )
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def override_db():
        async with sessions() as session:
            yield session

    api_app.dependency_overrides[get_db] = override_db
    headers = {"X-Shogun-Infrastructure-Token": str(settings.infrastructure_admin_token or "")}
    try:
        created = await client.post(
            "/api/v1/mapping-rpa/templates",
            headers=headers,
            json={
                "name": "Supplier Product PDF",
                "scope": "private",
                "owner_id": "system",
                "config": _config(),
            },
        )
        assert created.status_code == 201
        template_id = created.json()["data"]["id"]

        updated = await client.put(
            f"/api/v1/mapping-rpa/templates/{template_id}",
            headers=headers,
            json={"description": "Version two"},
        )
        assert updated.status_code == 200
        assert updated.json()["data"]["version"] == 2

        listed = await client.get("/api/v1/mapping-rpa/templates", headers=headers)
        assert [item["id"] for item in listed.json()["data"]] == [template_id]

        deleted = await client.delete(f"/api/v1/mapping-rpa/templates/{template_id}", headers=headers)
        assert deleted.json()["data"]["deleted"] is True
        listed = await client.get("/api/v1/mapping-rpa/templates", headers=headers)
        assert listed.json()["data"] == []
    finally:
        api_app.dependency_overrides.pop(get_db, None)
        await engine.dispose()
