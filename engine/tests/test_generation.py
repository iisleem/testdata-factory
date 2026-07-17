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
