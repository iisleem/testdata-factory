from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from uuid import UUID

import pytest

from testdata_factory_engine import GenerationError, generate_records, load_contract, validate_contract_data
from testdata_factory_engine.generation import DEFAULT_STRATEGIES, STRATEGIES


ROOT = Path(__file__).resolve().parents[2]
BUSINESS_TYPE_DATA_TYPES = {
    "integer": "integer",
    "quantity": "integer",
    "decimal": "decimal",
    "amount": "decimal",
    "percentage": "decimal",
    "boolean": "boolean",
    "enum": "enum",
    "date": "date",
    "date_of_birth": "date",
    "time": "time",
    "datetime": "datetime",
}


def _contract():
    return load_contract(ROOT / "examples" / "contracts" / "register.tdf.json")


def test_generate_records_is_repeatable() -> None:
    contract = _contract()

    first = generate_records(contract, "valid_signup", count=2, seed="suite")
    second = generate_records(contract, "valid_signup", count=2, seed="suite")

    assert first == second


def test_generate_records_changes_with_seed() -> None:
    contract = _contract()

    first = generate_records(contract, "valid_signup", seed="suite-a")
    second = generate_records(contract, "valid_signup", seed="suite-b")

    assert first != second


def test_positive_record_covers_common_business_types() -> None:
    record = generate_records(_contract(), "valid_signup", seed="suite")[0]

    assert set(record) == {"firstName", "email", "phone", "password", "age", "plan", "birthDate", "newsletter"}
    assert record["email"].endswith("@example.test")
    assert record["phone"].startswith("+155501")
    assert 18 <= record["age"] <= 99
    assert record["plan"] in {"basic", "pro", "enterprise"}
    assert isinstance(record["newsletter"], bool)


def test_negative_scenario_overrides_only_target_field() -> None:
    record = generate_records(_contract(), "invalid_email_format", seed="suite")[0]

    assert record["email"] == "not-an-email"
    assert record["phone"].startswith("+155501")
    assert record["password"].startswith("Tdf!")


def test_unknown_scenario_fails_clearly() -> None:
    with pytest.raises(GenerationError, match="Unknown scenario"):
        generate_records(_contract(), "missing_scenario")


def test_schema_business_types_have_registered_default_strategies() -> None:
    business_types = set(_schema_business_types())

    assert business_types - set(DEFAULT_STRATEGIES) == set()
    assert {strategy for strategy in DEFAULT_STRATEGIES.values() if strategy not in STRATEGIES} == set()


def test_default_generation_covers_all_schema_business_types() -> None:
    contract = _business_type_contract()
    validation = validate_contract_data(contract)

    first = generate_records(contract, "default_business_types", count=2, seed="coverage")
    second = generate_records(contract, "default_business_types", count=2, seed="coverage")

    assert validation.is_valid, validation.to_dict()
    assert first == second
    assert set(first[0]) == set(_schema_business_types())

    record = first[0]
    assert record["email"].endswith("@example.test")
    assert re.fullmatch(r"\+155501\d{4}", record["phone_number"])
    assert re.fullmatch(r"[A-Z]{2}", record["country_code"])
    assert re.fullmatch(r"\d{3} [A-Za-z ]+", record["address_line"])
    assert re.fullmatch(r"\d{5}", record["postal_code"])
    assert re.fullmatch(r"[A-Z]{3}", record["currency"])
    assert re.fullmatch(r"https://app-\d{3}\.example\.test/resource-1", record["url"])
    assert re.fullmatch(r"service-\d{3}\.example\.test", record["domain"])
    UUID(record["uuid"])
    assert re.fullmatch(r"NID-\d{9}", record["national_id"])
    assert re.fullmatch(r"[PTX]\d{8}", record["passport_number"])
    assert re.fullmatch(r"TAX-\d{8}", record["tax_id"])
    assert re.fullmatch(r"000\d{9}", record["account_number"])
    assert _iban_is_valid(record["iban"])
    assert record["credit_card_number"].startswith("411111")
    assert _luhn_is_valid(record["credit_card_number"])
    assert re.fullmatch(r"\d{3}", record["cvv"])
    assert re.fullmatch(r"\d{2}/3\d", record["expiry_date"])
    assert re.fullmatch(r"\d{6}", record["otp"])
    assert datetime.fromisoformat(record["datetime"].removesuffix("Z"))
    assert re.fullmatch(r"\d{2}:\d{2}:00", record["time"])


def test_security_and_robustness_strategies_generate_expected_values() -> None:
    contract = _advanced_contract()
    validation = validate_contract_data(contract)

    assert validation.is_valid, validation.to_dict()
    assert generate_records(contract, "xss_payloads", seed="advanced")[0]["notes"] == "<script>alert('tdf')</script>"
    assert generate_records(contract, "sql_injection_payloads", seed="advanced")[0]["notes"] == "admin' OR '1'='1"
    assert generate_records(contract, "null_required_fields", seed="advanced")[0]["email"] is None
    assert generate_records(contract, "empty_string_fields", seed="advanced")[0]["notes"] == ""
    assert generate_records(contract, "empty_dependent_date_field", seed="advanced")[0]["endDate"] == ""
    assert generate_records(contract, "whitespace_only_fields", seed="advanced")[0]["notes"] == "   "
    assert len(generate_records(contract, "below_min_length_fields", seed="advanced")[0]["notes"]) == 2
    assert len(generate_records(contract, "over_max_length_fields", seed="advanced")[0]["notes"]) == 11
    assert generate_records(contract, "boolean_false_boundaries", seed="advanced")[0]["marketingOptIn"] is False
    assert generate_records(contract, "boolean_true_boundaries", seed="advanced")[0]["marketingOptIn"] is True

    duplicate_records = generate_records(contract, "duplicate_unique_fields", count=2, seed="advanced")
    assert duplicate_records[0]["email"] == duplicate_records[1]["email"] == "duplicate@example.test"


def test_cross_field_dependencies_generate_valid_and_invalid_records() -> None:
    contract = _advanced_contract()

    happy_record = generate_records(contract, "valid_advanced", seed="advanced")[0]
    mismatch_record = generate_records(contract, "mismatched_confirmation_fields", seed="advanced")[0]
    invalid_date_record = generate_records(contract, "invalid_date_ranges", seed="advanced")[0]
    invalid_numeric_record = generate_records(contract, "invalid_numeric_ranges", seed="advanced")[0]
    normal_strategy_record = generate_records(contract, "normal_strategy_confirmation_matches", seed="advanced")[0]

    assert happy_record["confirmPassword"] == happy_record["password"]
    assert happy_record["endDate"] > happy_record["startDate"]
    assert happy_record["maxGuests"] >= happy_record["minGuests"]
    assert mismatch_record["confirmPassword"] != mismatch_record["password"]
    assert invalid_date_record["endDate"] < invalid_date_record["startDate"]
    assert invalid_numeric_record["maxGuests"] < invalid_numeric_record["minGuests"]
    assert normal_strategy_record["confirmPassword"] == normal_strategy_record["password"]
    assert normal_strategy_record["confirmPassword"] != "password"


def _schema_business_types() -> list[str]:
    schema = json.loads((ROOT / "specs" / "contract-schema" / "tdf-contract.schema.json").read_text(encoding="utf-8"))
    return schema["$defs"]["field"]["properties"]["businessType"]["enum"]


def _business_type_contract() -> dict:
    return {
        "schemaVersion": "1.0",
        "id": "business-type-defaults",
        "source": {
            "type": "manual",
            "value": "business-type-defaults",
        },
        "locale": {
            "language": "en",
            "country": "US",
        },
        "fields": {business_type: _business_type_field(business_type) for business_type in _schema_business_types()},
        "scenarios": [
            {
                "id": "default_business_types",
                "kind": "positive",
                "description": "Generate one value for every supported business type.",
                "fields": {},
            }
        ],
        "generation": {
            "deterministic": True,
            "defaultSeed": "business-type-suite",
        },
        "validation": {
            "status": "valid",
        },
    }


def _business_type_field(business_type: str) -> dict:
    field = {
        "dataType": BUSINESS_TYPE_DATA_TYPES.get(business_type, "string"),
        "businessType": business_type,
        "required": False,
    }
    if business_type == "enum":
        field["constraints"] = {"values": ["basic", "pro", "enterprise"]}
    elif business_type in {"integer", "quantity"}:
        field["constraints"] = {"minimum": 10, "maximum": 20}
    elif business_type in {"decimal", "amount", "percentage"}:
        field["constraints"] = {"minimum": 1, "maximum": 9}
    elif business_type == "phone_number":
        field["constraints"] = {"country": "US"}
    return field


def _advanced_contract() -> dict:
    return {
        "schemaVersion": "1.0",
        "id": "advanced-generation",
        "source": {
            "type": "manual",
            "value": "advanced-generation",
        },
        "locale": {
            "language": "en",
        },
        "fields": {
            "email": {
                "dataType": "string",
                "businessType": "email",
                "required": True,
                "constraints": {"format": "email", "unique": True},
            },
            "password": {
                "dataType": "string",
                "businessType": "password",
                "required": True,
                "constraints": {"minLength": 12, "maxLength": 72},
            },
            "confirmPassword": {
                "dataType": "string",
                "businessType": "password",
                "required": True,
                "constraints": {"minLength": 12, "maxLength": 72},
                "dependencies": {"matchesField": "password"},
            },
            "startDate": {
                "dataType": "date",
                "businessType": "date",
                "required": True,
                "dependencies": {"rangeStartFor": "endDate"},
            },
            "endDate": {
                "dataType": "date",
                "businessType": "date",
                "required": True,
                "dependencies": {"rangeEndFor": "startDate"},
            },
            "minGuests": {
                "dataType": "integer",
                "businessType": "integer",
                "required": True,
                "constraints": {"minimum": 1, "maximum": 5},
                "dependencies": {"minFor": "maxGuests"},
            },
            "maxGuests": {
                "dataType": "integer",
                "businessType": "integer",
                "required": True,
                "constraints": {"minimum": 1, "maximum": 10},
                "dependencies": {"maxFor": "minGuests"},
            },
            "notes": {
                "dataType": "string",
                "businessType": "free_text",
                "required": False,
                "constraints": {"minLength": 3, "maxLength": 10},
            },
            "marketingOptIn": {
                "dataType": "boolean",
                "businessType": "boolean",
                "required": False,
            },
        },
        "scenarios": [
            {"id": "valid_advanced", "kind": "positive", "description": "Valid advanced fields.", "fields": {}},
            {
                "id": "xss_payloads",
                "kind": "security",
                "description": "XSS probe.",
                "fields": {"notes": {"strategy": "xss_payload"}},
            },
            {
                "id": "sql_injection_payloads",
                "kind": "security",
                "description": "SQL injection probe.",
                "fields": {"notes": {"strategy": "sql_injection_payload"}},
            },
            {
                "id": "null_required_fields",
                "kind": "negative",
                "description": "Null required field.",
                "fields": {"email": {"strategy": "null_value"}},
            },
            {
                "id": "empty_string_fields",
                "kind": "negative",
                "description": "Empty string field.",
                "fields": {"notes": {"strategy": "empty_string"}},
            },
            {
                "id": "empty_dependent_date_field",
                "kind": "negative",
                "description": "Empty string on a dependent date field.",
                "fields": {"endDate": {"strategy": "empty_string"}},
            },
            {
                "id": "whitespace_only_fields",
                "kind": "negative",
                "description": "Whitespace-only field.",
                "fields": {"notes": {"strategy": "whitespace_only"}},
            },
            {
                "id": "below_min_length_fields",
                "kind": "negative",
                "description": "Below minimum length.",
                "fields": {"notes": {"strategy": "below_min_length"}},
            },
            {
                "id": "over_max_length_fields",
                "kind": "negative",
                "description": "Over maximum length.",
                "fields": {"notes": {"strategy": "over_max_length"}},
            },
            {
                "id": "duplicate_unique_fields",
                "kind": "negative",
                "description": "Duplicate unique field.",
                "fields": {"email": {"strategy": "duplicate_value"}},
            },
            {
                "id": "boolean_false_boundaries",
                "kind": "boundary",
                "description": "False boolean.",
                "fields": {"marketingOptIn": {"strategy": "boolean_false"}},
            },
            {
                "id": "boolean_true_boundaries",
                "kind": "boundary",
                "description": "True boolean.",
                "fields": {"marketingOptIn": {"strategy": "boolean_true"}},
            },
            {
                "id": "mismatched_confirmation_fields",
                "kind": "negative",
                "description": "Password confirmation mismatch.",
                "fields": {"confirmPassword": {"strategy": "mismatch_field"}},
            },
            {
                "id": "normal_strategy_confirmation_matches",
                "kind": "positive",
                "description": "Generated dependent fields honor dependencies after normal strategy generation.",
                "fields": {"confirmPassword": {"strategy": "weak_password"}},
            },
            {
                "id": "invalid_date_ranges",
                "kind": "negative",
                "description": "Date range is reversed.",
                "fields": {"endDate": {"strategy": "date_before_related_field"}},
            },
            {
                "id": "invalid_numeric_ranges",
                "kind": "negative",
                "description": "Maximum is below minimum.",
                "fields": {"maxGuests": {"strategy": "numeric_max_below_min"}},
            },
        ],
        "generation": {
            "deterministic": True,
            "defaultSeed": "advanced-generation-suite",
        },
        "validation": {
            "status": "valid",
        },
    }


def _iban_is_valid(value: str) -> bool:
    return re.fullmatch(r"GB\d{2}TEST\d{14}", value) is not None and _iban_mod97(value[4:] + value[:4]) == 1


def _iban_mod97(value: str) -> int:
    remainder = 0
    for char in value.upper():
        if char.isdigit():
            digits = char
        elif char.isalpha():
            digits = str(ord(char) - 55)
        else:
            return -1
        for digit in digits:
            remainder = (remainder * 10 + int(digit)) % 97
    return remainder


def _luhn_is_valid(value: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(value)):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0
