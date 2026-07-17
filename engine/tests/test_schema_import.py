from __future__ import annotations

import json
from pathlib import Path

import pytest

from testdata_factory_engine import (
    SchemaImportError,
    import_json_schema_contract,
    import_openapi_request_contract,
    validate_contract_data,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "engine" / "tests" / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_imports_json_schema_object_properties() -> None:
    contract = import_json_schema_contract(
        _load_fixture("customer.schema.json"),
        contract_id="customer-signup",
        source_value="customer.schema.json",
    )

    validate_contract_data(contract)
    assert contract["id"] == "customer-signup"
    assert contract["source"] == {"type": "json_schema", "value": "customer.schema.json"}

    fields = contract["fields"]
    assert fields["email"]["required"] is True
    assert fields["email"]["businessType"] == "email"
    assert fields["email"]["constraints"]["format"] == "email"
    assert fields["email"]["constraints"]["minLength"] == 5
    assert fields["email"]["constraints"]["maxLength"] == 120
    assert fields["email"]["constraints"]["description"] == "Primary customer email address."
    assert fields["email"]["constraints"]["examples"] == ["customer@example.test"]
    assert fields["plan"]["dataType"] == "enum"
    assert fields["plan"]["constraints"]["values"] == ["basic", "pro", "enterprise"]
    assert fields["age"]["constraints"]["minimum"] == 18
    assert fields["age"]["constraints"]["maximum"] == 99
    assert fields["birthDate"]["required"] is False
    assert fields["birthDate"]["dataType"] == "date"
    assert fields["birthDate"]["constraints"]["example"] == "1990-01-01"


def test_imports_openapi_selected_operation_request_schema() -> None:
    contract = import_openapi_request_contract(
        _load_fixture("customer.openapi.json"),
        "createCustomer",
        source_value="customer.openapi.json",
    )

    validate_contract_data(contract)
    assert contract["id"] == "create-customer"
    assert contract["source"] == {"type": "openapi", "value": "customer.openapi.json#createCustomer"}

    fields = contract["fields"]
    assert set(fields) == {"email", "password", "role", "profileId", "spendLimit", "marketingOptIn"}
    assert fields["email"]["required"] is True
    assert fields["email"]["businessType"] == "email"
    assert fields["role"]["businessType"] == "enum"
    assert fields["role"]["constraints"]["values"] == ["admin", "member"]
    assert fields["profileId"]["constraints"]["format"] == "uuid"
    assert fields["profileId"]["constraints"]["example"] == "123e4567-e89b-12d3-a456-426614174000"
    assert fields["spendLimit"]["businessType"] == "amount"
    assert fields["spendLimit"]["constraints"]["minimum"] == 0
    assert fields["spendLimit"]["constraints"]["maximum"] == 1000
    assert fields["marketingOptIn"]["required"] is False


def test_imports_openapi_operation_by_method_and_path() -> None:
    contract = import_openapi_request_contract(_load_fixture("customer.openapi.json"), "PATCH /v1/customers/{customerId}")

    assert contract["id"] == "update-customer"
    assert set(contract["fields"]) == {"displayName"}


def test_import_rejects_schema_without_object_properties() -> None:
    with pytest.raises(SchemaImportError, match="object schema with properties"):
        import_json_schema_contract({"type": "string"}, contract_id="invalid")
