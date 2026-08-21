"""Deterministic enterprise-profile execution and AgentFlow integration."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

import shogun.engine.flow_engine as flow_engine
from shogun.engine.flow_engine import _canonical_output_for_model, _exec_mapping_rpa
from shogun.mapping.errors import (
    MappingFieldMissing,
    MappingInputError,
    MappingSchemaError,
    MappingTypeError,
)
from shogun.mapping.schema import MappingConfig
from shogun.services.enterprise_transformations import (
    CANONICAL_ENTITY_ADAPTER,
    enterprise_profile_content_hash,
    execute_enterprise_profile,
    registered_transformation_adapters,
    validate_enterprise_profile_manifest,
)

PROFILE_DIR = (
    Path(__file__).resolve().parents[1]
    / "shogun"
    / "resources"
    / "transformation_profiles"
)


def _resource_profile(profile_id: str) -> dict:
    return json.loads(
        (PROFILE_DIR / f"{profile_id}.json").read_text(encoding="utf-8")
    )


def _product_profile(**overrides):
    profile = {
        "manifest_version": 1,
        "id": "microsoft.d365_fscm.odata.products_v2_to_product.v1",
        "version": "1.0.0",
        "lifecycle": "active",
        "title": "D365 Products V2 to canonical product",
        "profile_kind": "structured_ingress",
        "platform": {"vendor": "Microsoft", "product": "D365 F&SCM", "family": "ERP"},
        "source": {
            "transport": "odata",
            "api_version": "v2",
            "object": "ProductsV2",
            "record_shape": "collection",
            "record_path": "value",
            "pagination": "odata_next_link",
        },
        "canonical_contract": {"id": "product", "version": "1", "record_kind": "master"},
        "identity": {
            "source_key": ["ProductNumber"],
            "canonical_key": ["id"],
            "conflict_policy": "replace",
        },
        "field_map": [
            {
                "source": "ProductNumber",
                "target": "id",
                "type": "string",
                "required": True,
                "transforms": ["trim"],
            },
            {"source": "ProductName", "target": "name", "type": "string", "required": True},
            {
                "source": "AvailableQuantity",
                "target": "inventory.available",
                "type": "decimal",
                "required": True,
                "transforms": ["decimal_normalize"],
            },
            {
                "source": "CreatedDateTime",
                "target": "timestamps.created",
                "type": "datetime",
                "required": True,
                "transforms": ["datetime_normalize"],
            },
        ],
        "invariants": [
            {"id": "product-id", "rule": "required_nonempty", "fields": ["id"]},
            {"id": "available-quantity", "rule": "nonnegative", "field": "inventory.available"},
        ],
        "privacy": {
            "classification": "internal",
            "pii_fields": [],
            "secret_fields": [],
            "retention": "flow_policy",
        },
        "adapter": CANONICAL_ENTITY_ADAPTER,
        "parameters": {},
        "adapter_requirements": {
            "adapter": CANONICAL_ENTITY_ADAPTER,
            "minimum_version": 1,
            "status": "available",
            "capabilities": ["field_mapping", "canonical_envelope"],
            "fail_closed": True,
        },
        "selection": {
            "positive_fingerprints": ["object:ProductsV2", "field:ProductNumber"],
            "negative_fingerprints": ["field:IsSalesforceRecord=true"],
        },
    }
    profile.update(overrides)
    return profile


def _registry_evidence(profile, **overrides):
    evidence = {
        "profile_id": profile["id"],
        "version": 1,
        "content_hash": enterprise_profile_content_hash(profile),
        "status": "active",
        "adapter_id": profile["adapter"],
        "adapter_status": "available",
    }
    evidence.update(overrides)
    return evidence


def test_adapter_catalog_exposes_structured_and_sectioned_matrix_adapters():
    adapters = registered_transformation_adapters()
    assert adapters[CANONICAL_ENTITY_ADAPTER]["status"] == "available"
    assert adapters["sectioned_record_matrix_v1"]["status"] == "available"


def test_manifest_validation_preserves_enterprise_metadata_and_rejects_secrets():
    normalized = validate_enterprise_profile_manifest(_product_profile())
    assert normalized["platform"]["product"] == "D365 F&SCM"
    assert normalized["canonical_contract"]["id"] == "product"

    unsafe = _product_profile(parameters={"client_secret": "must-never-live-in-a-profile"})
    with pytest.raises(MappingSchemaError, match="cannot contain credentials"):
        validate_enterprise_profile_manifest(unsafe)


def test_manifest_validation_is_strict_about_nested_types_and_available_adapter_contract():
    aliases_are_not_a_list = _product_profile()
    aliases_are_not_a_list["field_map"][0]["aliases"] = "ProductId"
    with pytest.raises(MappingSchemaError, match="must be a list"):
        validate_enterprise_profile_manifest(aliases_are_not_a_list)

    minimum_version_is_unavailable = _product_profile()
    minimum_version_is_unavailable["adapter_requirements"]["minimum_version"] = 3
    with pytest.raises(MappingSchemaError, match="runtime version is 2"):
        validate_enterprise_profile_manifest(minimum_version_is_unavailable)

    unsupported_capability = _product_profile()
    unsupported_capability["adapter_requirements"]["capabilities"].append("cross_object_join")
    with pytest.raises(MappingSchemaError, match="cross_object_join"):
        validate_enterprise_profile_manifest(unsupported_capability)

    non_boolean_fail_closed = _product_profile()
    non_boolean_fail_closed["adapter_requirements"]["fail_closed"] = "true"
    with pytest.raises(MappingSchemaError, match="must be a boolean"):
        validate_enterprise_profile_manifest(non_boolean_fail_closed)


def test_manifest_validation_rejects_malformed_fingerprint_syntax():
    malformed = _product_profile()
    malformed["selection"]["positive_fingerprints"] = ["transport=odata"]
    with pytest.raises(MappingSchemaError, match="explicit field: or path: prefix"):
        validate_enterprise_profile_manifest(malformed)


def test_profile_maps_odata_records_deduplicates_and_neutralizes_excel_formulas():
    payload = {
        "value": [
            {
                "ProductNumber": " P-100 ",
                "ProductName": "Pump",
                "AvailableQuantity": "1.234,50",
                "CreatedDateTime": "2026-08-19T08:30:00",
            },
            {
                "ProductNumber": "P-100",
                "ProductName": "=2+2",
                "AvailableQuantity": "2,5",
                "CreatedDateTime": "2026-08-19T09:30:00",
            },
        ]
    }

    result = execute_enterprise_profile(
        (profile := _product_profile()),
        payload,
        context={"flow_id": "flow-1", "node_id": "profile-1", "source_node_id": "odata-1"},
        registry_evidence=_registry_evidence(profile),
    )

    assert result["status"] == "SUCCESS"
    assert result["records_received"] == 2
    assert result["records_written"] == 1
    assert result["canonical"]["records"] == [
        {
            "id": "P-100",
            "name": "=2+2",
            "inventory": {"available": 2.5},
            "timestamps": {"created": "2026-08-19T09:30:00"},
        }
    ]
    assert result["rows"] == [["P-100", "'=2+2", 2.5, "2026-08-19T09:30:00"]]
    assert result["lineage"][0]["flow_id"] == "flow-1"


def test_merge_deduplication_rerenders_rows_and_combines_lineage():
    profile = _product_profile()
    profile["identity"]["conflict_policy"] = "merge"
    profile["field_map"][1]["required"] = False
    payload = {
        "value": [
            {
                "ProductNumber": "P-100",
                "ProductName": "Pump",
                "AvailableQuantity": 1,
                "CreatedDateTime": "2026-08-19T08:30:00",
            },
            {
                "ProductNumber": "P-100",
                "AvailableQuantity": 2.5,
                "CreatedDateTime": "2026-08-19T09:30:00",
            },
        ]
    }

    result = execute_enterprise_profile(
        profile, payload, registry_evidence=_registry_evidence(profile)
    )

    assert result["canonical"]["records"] == [
        {
            "id": "P-100",
            "name": "Pump",
            "inventory": {"available": 2.5},
            "timestamps": {"created": "2026-08-19T09:30:00"},
        }
    ]
    assert result["rows"] == [["P-100", "Pump", 2.5, "2026-08-19T09:30:00"]]
    assert result["lineage"][0]["source_record_indices"] == [0, 1]
    assert [item["record_index"] for item in result["lineage"][0]["source_records"]] == [0, 1]


def test_entity_payload_with_business_items_is_not_guessed_as_a_collection_wrapper():
    profile = _product_profile()
    profile["source"].pop("record_path")
    profile["source"]["record_shape"] = "entity"
    profile["field_map"].append(
        {
            "source": "items.0.sku",
            "target": "first_line_sku",
            "type": "string",
            "required": True,
        }
    )
    entity = {
        "ProductNumber": "P-100",
        "ProductName": "Pump",
        "AvailableQuantity": 1,
        "CreatedDateTime": "2026-08-19",
        "items": [{"sku": "LINE-1"}, {"sku": "LINE-2"}],
    }

    result = execute_enterprise_profile(
        profile, entity, registry_evidence=_registry_evidence(profile)
    )

    assert result["records_received"] == 1
    assert result["canonical"]["records"][0]["first_line_sku"] == "LINE-1"
    with pytest.raises(MappingInputError, match="positive fingerprint"):
        execute_enterprise_profile(
            profile,
            {"value": [entity]},
            registry_evidence=_registry_evidence(profile),
        )


def test_header_lines_flatten_across_declared_page_wrappers_and_reconcile():
    profile = _resource_profile("business_central_sales_invoice_v1")
    first_header = {
        "id": "INV-1",
        "number": "1001",
        "customerId": "CUSTOMER-1",
        "invoiceDate": "2026-08-01",
        "currencyCode": "eur",
        "totalAmountExcludingTax": 30,
        "salesInvoiceLines": [
            {"id": "L-1", "itemId": "P-1", "quantity": 1, "netAmount": 10},
            {"id": "L-2", "itemId": "P-2", "quantity": 2, "netAmount": 20},
        ],
    }
    second_header = deepcopy(first_header)
    second_header.update({"id": "INV-2", "number": "1002"})
    second_header["salesInvoiceLines"] = [
        {"id": "L-1", "itemId": "P-3", "quantity": 3, "netAmount": 30}
    ]

    result = execute_enterprise_profile(
        profile,
        [{"value": [first_header]}, {"value": [second_header]}],
        registry_evidence=_registry_evidence(profile),
    )

    assert result["records_received"] == 3
    assert result["records_written"] == 3
    assert [record["line_id"] for record in result["canonical"]["records"]] == [
        "L-1",
        "L-2",
        "L-1",
    ]
    assert result["lineage"][2]["page_index"] == 1
    assert result["lineage"][2]["header_index"] == 1
    assert result["lineage"][2]["line_index"] == 0

    first_header["totalAmountExcludingTax"] = 31
    with pytest.raises(MappingSchemaError, match="does not reconcile"):
        execute_enterprise_profile(
            profile,
            {"value": [first_header]},
            registry_evidence=_registry_evidence(profile),
        )


def test_nested_related_path_and_synthetic_line_index_execute_without_guessing():
    netsuite = _resource_profile("netsuite_purchase_order_v1")
    result = execute_enterprise_profile(
        netsuite,
        {
            "items": [
                {
                    "id": "PO-1",
                    "tranId": "PO1001",
                    "entity": {"id": "VENDOR-1"},
                    "tranDate": "2026-08-01",
                    "status": {"id": "OPEN"},
                    "item": {
                        "items": [
                            {
                                "line": "1",
                                "item": {"id": "P-1"},
                                "quantity": 4,
                            }
                        ]
                    },
                }
            ]
        },
        registry_evidence=_registry_evidence(netsuite),
    )
    assert result["canonical"]["records"][0]["product_id"] == "P-1"
    assert result["lineage"][0]["related_object_path"] == "item.items"

    xero = _resource_profile("xero_manual_journal_v1")
    journal = {
        "ManualJournalID": "J-1",
        "Date": "2026-08-01",
        "Status": "POSTED",
        "UpdatedDateUTC": "2026-08-01T12:00:00",
        "JournalLines": [
            {"AccountCode": "1000", "LineAmount": 10},
            {"AccountCode": "2000", "LineAmount": -10},
        ],
    }
    xero_result = execute_enterprise_profile(
        xero,
        {"ManualJournals": [journal]},
        registry_evidence=_registry_evidence(xero),
    )
    assert [record["line_id"] for record in xero_result["canonical"]["records"]] == [0, 1]

    journal["JournalLines"][1]["LineAmount"] = -9
    with pytest.raises(MappingSchemaError, match="sums to"):
        execute_enterprise_profile(
            xero,
            {"ManualJournals": [journal]},
            registry_evidence=_registry_evidence(xero),
        )


def test_declared_heterogeneous_union_stamps_and_checks_object_discriminator():
    profile = _resource_profile("quickbooks_online_bank_transaction_v1")

    def transaction(identifier: str, amount: int) -> dict:
        return {
            "Id": identifier,
            "TxnDate": "2026-08-01",
            "TotalAmt": amount,
            "MetaData": {"LastUpdatedTime": "2026-08-01T12:00:00"},
        }

    result = execute_enterprise_profile(
        profile,
        {
            "QueryResponse": {
                "Purchase": [transaction("P-1", 10)],
                "Deposit": [transaction("D-1", 20)],
            }
        },
        registry_evidence=_registry_evidence(profile),
    )

    assert [
        record["transaction_type"] for record in result["canonical"]["records"]
    ] == ["Purchase", "Deposit"]
    assert [item["union_path"] for item in result["lineage"]] == [
        "QueryResponse.Purchase",
        "QueryResponse.Deposit",
    ]

    conflicting = transaction("P-2", 5)
    conflicting["TxnType"] = "Deposit"
    with pytest.raises(MappingInputError, match="discriminator"):
        execute_enterprise_profile(
            profile,
            {"QueryResponse": {"Purchase": [conflicting]}},
            registry_evidence=_registry_evidence(profile),
        )


def test_cross_line_and_per_line_business_rules_fail_closed():
    journal_profile = _resource_profile("quickbooks_online_journal_entry_v1")
    journal = {
        "Id": "J-1",
        "TxnDate": "2026-08-01",
        "Line": [
            {
                "Id": "1",
                "Amount": 100,
                "JournalEntryLineDetail": {
                    "AccountRef": {"value": "1000"},
                    "PostingType": "Debit",
                },
            },
            {
                "Id": "2",
                "Amount": 100,
                "JournalEntryLineDetail": {
                    "AccountRef": {"value": "2000"},
                    "PostingType": "Credit",
                },
            },
        ],
    }
    execute_enterprise_profile(
        journal_profile,
        {"QueryResponse": {"JournalEntry": [journal]}},
        registry_evidence=_registry_evidence(journal_profile),
    )
    journal["Line"][1]["Amount"] = 99
    with pytest.raises(MappingSchemaError, match="do not reconcile"):
        execute_enterprise_profile(
            journal_profile,
            {"QueryResponse": {"JournalEntry": [journal]}},
            registry_evidence=_registry_evidence(journal_profile),
        )

    bom_profile = _resource_profile("d365_fscm_bom_v1")
    bom = {
        "dataAreaId": "USMF",
        "BillOfMaterialsId": "BOM-1",
        "BillOfMaterialsLines": [
            {"LineNumber": "1", "ItemNumber": "P-1", "Quantity": 0}
        ],
    }
    with pytest.raises(MappingSchemaError, match="greater than"):
        execute_enterprise_profile(
            bom_profile,
            {"value": [bom]},
            registry_evidence=_registry_evidence(bom_profile),
        )

    ledger_profile = _resource_profile("d365_fscm_general_journal_v1")
    ledger = {
        "dataAreaId": "USMF",
        "JournalBatchNumber": "BATCH-1",
        "GeneralJournalAccountEntries": [
            {
                "LineNumber": "1",
                "TransDate": "2026-08-01",
                "LedgerAccount": "1000",
                "CurrencyCode": "USD",
                "DebitAmount": 10,
                "CreditAmount": 10,
            }
        ],
    }
    with pytest.raises(MappingSchemaError, match="cannot both be nonzero"):
        execute_enterprise_profile(
            ledger_profile,
            {"value": [ledger]},
            registry_evidence=_registry_evidence(ledger_profile),
        )


def test_positive_field_fingerprint_must_match_every_record():
    payload = {
        "value": [
            {
                "ProductNumber": "P-100",
                "ProductName": "Pump",
                "AvailableQuantity": 1,
                "CreatedDateTime": "2026-08-19",
            },
            {
                "WrongNumber": "P-200",
                "ProductName": "Valve",
                "AvailableQuantity": 2,
                "CreatedDateTime": "2026-08-19",
            },
        ]
    }

    with pytest.raises(MappingInputError, match="field:ProductNumber"):
        profile = _product_profile()
        execute_enterprise_profile(
            profile, payload, registry_evidence=_registry_evidence(profile)
        )


def test_identity_fields_must_be_present_and_non_blank_before_and_after_mapping():
    blank_source = {
        "value": [
            {
                "ProductNumber": "   ",
                "ProductName": "Pump",
                "AvailableQuantity": 1,
                "CreatedDateTime": "2026-08-19",
            }
        ]
    }
    with pytest.raises(MappingFieldMissing, match="Source identity"):
        profile = _product_profile()
        execute_enterprise_profile(
            profile, blank_source, registry_evidence=_registry_evidence(profile)
        )

    blank_canonical_profile = _product_profile()
    blank_canonical_profile["field_map"][0]["transforms"] = [
        {"name": "replace", "options": {"old": "P-100", "new": ""}}
    ]
    nonblank_source = {
        "value": [
            {
                "ProductNumber": "P-100",
                "ProductName": "Pump",
                "AvailableQuantity": 1,
                "CreatedDateTime": "2026-08-19",
            }
        ]
    }
    with pytest.raises(MappingFieldMissing, match="Canonical identity"):
        execute_enterprise_profile(
            blank_canonical_profile,
            nonblank_source,
            registry_evidence=_registry_evidence(blank_canonical_profile),
        )


def test_nonnegative_invariant_reports_a_typed_mapping_error():
    profile = _product_profile()
    profile["field_map"][2]["type"] = "any"
    profile["field_map"][2]["transforms"] = []
    payload = {
        "value": [
            {
                "ProductNumber": "P-100",
                "ProductName": "Pump",
                "AvailableQuantity": "not-a-number",
                "CreatedDateTime": "2026-08-19",
            }
        ]
    }

    with pytest.raises(MappingTypeError, match="is not numeric") as exc_info:
        execute_enterprise_profile(
            profile, payload, registry_evidence=_registry_evidence(profile)
        )
    assert exc_info.value.field == "inventory.available"
    assert exc_info.value.record_index == 0


def test_profile_selection_and_lifecycle_fail_closed():
    wrong_payload = {
        "value": [
            {
                "WrongNumber": "P-100",
                "ProductName": "Pump",
                "AvailableQuantity": 1,
                "CreatedDateTime": "2026-08-19",
            }
        ]
    }
    with pytest.raises(MappingInputError, match="positive fingerprint"):
        profile = _product_profile()
        execute_enterprise_profile(
            profile,
            wrong_payload,
            registry_evidence=_registry_evidence(profile),
        )

    planned_adapter = _product_profile()
    planned_adapter["adapter_requirements"]["status"] = "planned"
    with pytest.raises(MappingSchemaError, match="requires unavailable adapter"):
        execute_enterprise_profile(
            planned_adapter,
            {"value": []},
            registry_evidence=_registry_evidence(planned_adapter),
        )


def test_canonical_model_context_is_single_copy_and_redacts_declared_pii():
    profile = _product_profile()
    profile["privacy"]["pii_fields"] = ["name"]
    result = execute_enterprise_profile(
        profile,
        {
            "value": [
                {
                    "ProductNumber": "P-100",
                    "ProductName": "Sensitive product alias",
                    "AvailableQuantity": 1,
                    "CreatedDateTime": "2026-08-19",
                }
            ]
        },
        registry_evidence=_registry_evidence(profile),
    )

    rendered = _canonical_output_for_model(result)

    assert "Sensitive product alias" not in rendered
    assert "[REDACTED FOR MODEL CONTEXT]" in rendered
    assert '"rows"' not in rendered
    assert '"lineage"' not in rendered
    assert rendered.count('"P-100"') == 1

    planned = _product_profile(lifecycle="candidate")
    with pytest.raises(MappingSchemaError, match="must be resolved through the governed registry"):
        execute_enterprise_profile(
            planned,
            {
                "value": [
                    {
                        "ProductNumber": "P-100",
                        "ProductName": "Pump",
                        "AvailableQuantity": 1,
                        "CreatedDateTime": "2026-08-19",
                    }
                ]
            },
        )


def test_profile_mode_schema_preserves_manifest_and_rejects_ambiguous_rules():
    config = MappingConfig.model_validate(
        {
            "execution_mode": "profile",
            "output": {"type": "range", "start_cell": "B3", "sheet": "Products"},
            "transformation_profile": _product_profile(),
        }
    )
    dumped = config.model_dump(mode="json")
    assert dumped["transformation_profile"]["platform"]["vendor"] == "Microsoft"
    assert dumped["transformation_profile"]["field_map"][0]["target"] == "id"

    with pytest.raises(ValueError, match="mappings must be empty"):
        MappingConfig.model_validate(
            {
                "execution_mode": "profile",
                "mappings": [{"source": "ProductNumber", "target": "A"}],
                "transformation_profile": _product_profile(),
            }
        )


@pytest.mark.anyio
async def test_agentflow_profile_mode_executes_to_canonical_and_excel_envelope(monkeypatch):
    profile = _product_profile()

    async def resolve(_profile):
        return profile, _registry_evidence(profile)

    monkeypatch.setattr(flow_engine, "_resolve_registered_enterprise_profile", resolve)
    result = await _exec_mapping_rpa(
        {
            "name": "D365 product ingress",
            "execution_mode": "profile",
            "output": {"type": "range", "start_cell": "B3", "sheet": "Products"},
            "transformation_profile": profile,
        },
        {
            "odata": {
                "value": [
                    {
                        "ProductNumber": "P-100",
                        "ProductName": "Pump",
                        "AvailableQuantity": 5,
                        "CreatedDateTime": "2026-08-19",
                    }
                ]
            }
        },
        flow_id="flow-1",
        node_id="profile-1",
    )

    assert result["__shogun_canonical_output__"] is True
    assert result["canonical"]["contract"] == {"id": "product", "version": "1"}
    assert result["rows"][0][:3] == ["P-100", "Pump", 5]
    assert result["start_cell"] == "B3"
    assert result["sheet"] == "Products"


@pytest.mark.anyio
async def test_agentflow_profile_mode_routes_unavailable_profile_error(monkeypatch):
    profile = deepcopy(_product_profile())
    profile["adapter_requirements"]["status"] = "planned"

    async def resolve(_profile):
        return profile, _registry_evidence(profile, adapter_status="unavailable")

    monkeypatch.setattr(flow_engine, "_resolve_registered_enterprise_profile", resolve)
    result = await _exec_mapping_rpa(
        {
            "execution_mode": "profile",
            "transformation_profile": profile,
        },
        {
            "odata": {
                "value": [
                    {
                        "ProductNumber": "P-100",
                        "ProductName": "Pump",
                        "AvailableQuantity": 5,
                        "CreatedDateTime": "2026-08-19",
                    }
                ]
            }
        },
        flow_id="flow-1",
        node_id="profile-1",
    )

    assert result["status"] == "MAPPING_SCHEMA_ERROR"
    assert result["mapping"]["execution_mode"] == "profile"
    assert result["mapping"]["profile_id"] == profile["id"]
