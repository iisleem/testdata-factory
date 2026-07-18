from __future__ import annotations

import json
from pathlib import Path

import pytest

from testdata_factory_engine import (
    SchemaImportError,
    generate_records,
    import_json_schema_contract,
    import_openapi_request_contract,
    validate_contract_data,
)
from testdata_factory_engine import schema_import


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

    validation = validate_contract_data(contract)
    assert validation.is_valid, validation.to_dict()
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

    scenarios = {scenario["id"]: scenario for scenario in contract["scenarios"]}
    assert list(scenarios) == [
        "valid_payload",
        "invalid_email_format",
        "missing_required_fields",
        "min_length_boundaries",
        "max_length_boundaries",
        "numeric_minimum_boundaries",
        "numeric_maximum_boundaries",
        "enum_value_boundaries",
        "date_boundaries",
    ]
    assert scenarios["valid_payload"]["fields"]["email"]["strategy"] == "valid_email"
    assert scenarios["valid_payload"]["fields"]["plan"]["strategy"] == "valid_enum"
    assert scenarios["missing_required_fields"]["fields"] == {
        "email": {"strategy": "missing_required"},
        "plan": {"strategy": "missing_required"},
        "age": {"strategy": "missing_required"},
    }
    assert scenarios["numeric_minimum_boundaries"]["fields"]["age"]["value"] == 18
    assert scenarios["numeric_maximum_boundaries"]["fields"]["age"]["value"] == 99
    assert scenarios["enum_value_boundaries"]["fields"]["plan"]["value"] == "basic"
    assert scenarios["date_boundaries"]["fields"]["birthDate"]["value"] == "1990-01-01"

    happy_record = generate_records(contract, "valid_payload", seed="schema-suite")[0]
    invalid_email_record = generate_records(contract, "invalid_email_format", seed="schema-suite")[0]
    minimum_record = generate_records(contract, "numeric_minimum_boundaries", seed="schema-suite")[0]

    assert happy_record["email"].endswith("@example.test")
    assert happy_record["plan"] in {"basic", "pro", "enterprise"}
    assert 18 <= happy_record["age"] <= 99
    assert invalid_email_record["email"] == "not-an-email"
    assert minimum_record["age"] == 18


def test_imports_openapi_selected_operation_request_schema() -> None:
    contract = import_openapi_request_contract(
        _load_fixture("customer.openapi.json"),
        "createCustomer",
        source_value="customer.openapi.json",
    )

    validation = validate_contract_data(contract)
    assert validation.is_valid, validation.to_dict()
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
    assert fields["marketingOptIn"]["businessType"] == "boolean"
    assert contract["scenarios"][0]["fields"]["profileId"]["strategy"] == "valid_uuid"
    assert contract["scenarios"][0]["fields"]["marketingOptIn"]["strategy"] == "valid_boolean"

    scenarios = {scenario["id"]: scenario for scenario in contract["scenarios"]}
    assert list(scenarios) == [
        "valid_payload",
        "invalid_email_format",
        "weak_password",
        "missing_required_fields",
        "min_length_boundaries",
        "max_length_boundaries",
        "numeric_minimum_boundaries",
        "numeric_maximum_boundaries",
        "enum_value_boundaries",
    ]
    assert scenarios["valid_payload"]["fields"]["password"]["strategy"] == "valid_password"
    assert scenarios["weak_password"]["fields"] == {"password": {"strategy": "weak_password"}}
    assert scenarios["missing_required_fields"]["fields"] == {
        "email": {"strategy": "missing_required"},
        "password": {"strategy": "missing_required"},
        "role": {"strategy": "missing_required"},
    }
    assert scenarios["min_length_boundaries"]["fields"]["password"]["value"] == "Tdf!0000Pass"
    assert scenarios["numeric_maximum_boundaries"]["fields"]["spendLimit"]["value"] == 1000

    happy_record = generate_records(contract, "valid_payload", seed="openapi-suite")[0]
    weak_password_record = generate_records(contract, "weak_password", seed="openapi-suite")[0]
    missing_record = generate_records(contract, "missing_required_fields", seed="openapi-suite")[0]

    assert happy_record["email"].endswith("@example.test")
    assert happy_record["password"].startswith("Tdf!")
    assert happy_record["role"] in {"admin", "member"}
    assert weak_password_record["password"] == "password"
    assert "email" not in missing_record
    assert "password" not in missing_record
    assert "role" not in missing_record


def test_imports_openapi_operation_by_method_and_path() -> None:
    contract = import_openapi_request_contract(_load_fixture("customer.openapi.json"), "PATCH /v1/customers/{customerId}")

    assert contract["id"] == "update-customer"
    assert set(contract["fields"]) == {"displayName"}


def test_import_rejects_schema_without_object_properties() -> None:
    with pytest.raises(SchemaImportError, match="object schema with properties"):
        import_json_schema_contract({"type": "string"}, contract_id="invalid")


def test_import_rejects_invalid_validation_result(monkeypatch: pytest.MonkeyPatch) -> None:
    class Finding:
        severity = "error"
        field = "fields.email"
        message = "Invalid imported field."

    class Result:
        is_valid = False
        status = "invalid"
        findings = (Finding(),)

    monkeypatch.setattr(schema_import, "validate_contract_data", lambda contract: Result())

    with pytest.raises(SchemaImportError, match="Imported contract is invalid: fields.email"):
        import_json_schema_contract(_load_fixture("customer.schema.json"), contract_id="customer-signup")
