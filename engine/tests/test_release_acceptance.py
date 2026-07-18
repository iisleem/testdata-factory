from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import pytest

from testdata_factory_engine import (
    generate_records,
    import_json_schema_contract,
    import_openapi_request_contract,
    validate_contract_data,
)
from testdata_factory_engine.scanner import build_contract_draft, controls_from_payload


ACCEPTANCE_THRESHOLD = 0.75
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_PATTERN = re.compile(r"^\+\d{10,}$")
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
EXPIRY_PATTERN = re.compile(r"^(0[1-9]|1[0-2])/\d{2}$")


FieldExpectations = dict[str, str]


@pytest.fixture(scope="module")
def acceptance_contracts() -> dict[str, dict[str, Any]]:
    return {
        "registration_profile_contact_form": _registration_profile_contact_form_contract(),
        "checkout_payment_form": _checkout_payment_form_contract(),
        "customer_account_json_schema": import_json_schema_contract(
            _customer_account_schema(),
            contract_id="release-customer-account",
            source_value="acceptance/customer-account.schema.json",
        ),
        "booking_order_openapi": import_openapi_request_contract(
            _booking_order_openapi(),
            "createBookingOrder",
            contract_id="release-booking-order",
            source_value="acceptance/booking-order.openapi.json",
        ),
    }


def test_release_1_business_type_acceptance_score(acceptance_contracts: dict[str, dict[str, Any]]) -> None:
    expected = _expected_business_types()
    misses: list[str] = []
    total = 0

    for contract_name, field_expectations in expected.items():
        contract = acceptance_contracts[contract_name]
        fields = contract["fields"]
        for field_name, expected_type in field_expectations.items():
            total += 1
            actual_type = fields[field_name]["businessType"]
            if actual_type != expected_type:
                misses.append(f"{contract_name}.{field_name}: expected {expected_type}, got {actual_type}")

    matched = total - len(misses)
    score = matched / total

    assert total >= 30
    assert score >= ACCEPTANCE_THRESHOLD, (
        f"Release 1 businessType acceptance score {matched}/{total} = {score:.1%}; "
        f"threshold is {ACCEPTANCE_THRESHOLD:.0%}. Misses: {misses}"
    )

    for contract_name, field_expectations in expected.items():
        contract = acceptance_contracts[contract_name]
        for field_name, expected_type in field_expectations.items():
            assert contract["fields"][field_name]["businessType"] == expected_type


@pytest.mark.parametrize(
    ("contract_name", "positive_id", "negative_ids", "boundary_ids"),
    [
        (
            "registration_profile_contact_form",
            "valid_form",
            {"invalid_email_format", "invalid_phone_format", "weak_password", "missing_required_fields"},
            {"min_length_boundaries", "max_length_boundaries", "enum_value_boundaries", "date_boundaries"},
        ),
        (
            "checkout_payment_form",
            "valid_form",
            {"invalid_email_format", "invalid_phone_format", "missing_required_fields"},
            {"min_length_boundaries", "max_length_boundaries", "numeric_minimum_boundaries", "enum_value_boundaries"},
        ),
        (
            "customer_account_json_schema",
            "valid_payload",
            {"invalid_email_format", "invalid_phone_format", "weak_password", "missing_required_fields"},
            {"min_length_boundaries", "max_length_boundaries", "numeric_minimum_boundaries", "enum_value_boundaries", "date_boundaries"},
        ),
        (
            "booking_order_openapi",
            "valid_payload",
            {"invalid_email_format", "invalid_phone_format", "missing_required_fields"},
            {"min_length_boundaries", "max_length_boundaries", "numeric_minimum_boundaries", "enum_value_boundaries", "date_boundaries"},
        ),
    ],
)
def test_release_1_contracts_include_usable_scenarios(
    acceptance_contracts: dict[str, dict[str, Any]],
    contract_name: str,
    positive_id: str,
    negative_ids: set[str],
    boundary_ids: set[str],
) -> None:
    contract = acceptance_contracts[contract_name]
    validation = validate_contract_data(contract)
    assert validation.is_valid, validation.to_dict()

    scenarios = {scenario["id"]: scenario for scenario in contract["scenarios"]}
    assert positive_id in scenarios
    assert negative_ids <= scenarios.keys()
    assert boundary_ids <= scenarios.keys()

    happy_record = generate_records(contract, positive_id, seed=f"{contract_name}-happy")[0]
    _assert_happy_record(contract_name, happy_record)

    for scenario_id in sorted(negative_ids):
        negative_record = generate_records(contract, scenario_id, seed=f"{contract_name}-{scenario_id}")[0]
        _assert_negative_record(scenarios[scenario_id], negative_record)

    for scenario_id in sorted(boundary_ids):
        boundary_record = generate_records(contract, scenario_id, seed=f"{contract_name}-{scenario_id}")[0]
        _assert_boundary_record(contract, scenarios[scenario_id], boundary_record)


def _registration_profile_contact_form_contract() -> dict[str, Any]:
    controls = controls_from_payload(
        [
            _input("firstName", "First name", "text", required=True, autocomplete="given-name", minlength=2, maxlength=40),
            _input("lastName", "Last name", "text", required=True, autocomplete="family-name", minlength=2, maxlength=40),
            _input("displayName", "Display name", "text", autocomplete="name", minlength=3, maxlength=80),
            _input("email", "Email address", "email", required=True, autocomplete="email", minlength=5, maxlength=120),
            _input("password", "Password", "password", required=True, minlength=12, maxlength=72),
            _input("mobilePhone", "Mobile phone", "tel", required=True, autocomplete="tel"),
            _input("dateOfBirth", "Date of birth", "date", required=True, validation={"min": "1900-01-01", "max": "2010-12-31"}),
            _input("streetAddress", "Street address", "text", required=True, autocomplete="street-address", minlength=5, maxlength=120),
            _input("city", "City", "text", required=True, autocomplete="address-level2"),
            _input("postalCode", "Postal code", "text", required=True, autocomplete="postal-code", minlength=5, maxlength=10),
            _input("countryCode", "Country code", "text", required=True, autocomplete="country", minlength=2, maxlength=2),
            _select("contactPreference", "Contact preference", ["email", "sms", "phone"], required=True),
        ]
    )
    return build_contract_draft(
        controls,
        source="https://example.test/register",
        contract_id="Release Registration Profile Contact Form",
        locale_country="us",
    )


def _checkout_payment_form_contract() -> dict[str, Any]:
    controls = controls_from_payload(
        [
            _input("email", "Receipt email", "email", required=True, autocomplete="email", minlength=5, maxlength=120),
            _input("billingPhone", "Billing phone", "tel", required=True, autocomplete="tel"),
            _input("cardholderFullName", "Full name on card", "text", required=True, autocomplete="name", minlength=3, maxlength=80),
            _input("cardNumber", "Credit card number", "text", required=True, minlength=16, maxlength=19),
            _input("cardCvv", "CVV", "text", required=True, minlength=3, maxlength=4),
            _input("cardExpiry", "Expiry date", "text", required=True, minlength=5, maxlength=5),
            _input("billingAddress", "Billing address line 1", "text", required=True, autocomplete="address-line1", minlength=5, maxlength=120),
            _input("billingCity", "Billing city", "text", required=True, autocomplete="address-level2"),
            _input("billingPostalCode", "Billing postal code", "text", required=True, autocomplete="postal-code", minlength=5, maxlength=10),
            _input("billingCountry", "Billing country", "text", required=True, autocomplete="country-name"),
            _input("orderQuantity", "Quantity", "number", required=True, validation={"min": "1", "max": "10", "step": "1"}),
            _input("orderTotal", "Order total amount", "number", required=True, validation={"min": "1", "max": "5000", "step": "0.01"}),
            _select("shippingMethod", "Shipping method", ["standard", "express", "overnight"], required=True),
        ]
    )
    return build_contract_draft(
        controls,
        source="https://example.test/checkout",
        contract_id="Release Checkout Payment Form",
        locale_country="us",
    )


def _customer_account_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Customer account",
        "type": "object",
        "required": [
            "customerId",
            "emailAddress",
            "password",
            "phoneNumber",
            "firstName",
            "lastName",
            "accountStatus",
            "spendLimit",
        ],
        "properties": {
            "customerId": {"type": "string", "format": "uuid"},
            "emailAddress": {"type": "string", "format": "email", "minLength": 5, "maxLength": 120},
            "password": {"type": "string", "minLength": 12, "maxLength": 72},
            "phoneNumber": {"type": "string", "minLength": 10, "maxLength": 20},
            "firstName": {"type": "string", "minLength": 2, "maxLength": 40},
            "lastName": {"type": "string", "minLength": 2, "maxLength": 40},
            "dateOfBirth": {"type": "string", "format": "date", "example": "1990-01-01"},
            "addressLine1": {"type": "string", "minLength": 5, "maxLength": 120},
            "city": {"type": "string"},
            "postalCode": {"type": "string", "minLength": 5, "maxLength": 10},
            "countryCode": {"type": "string", "minLength": 2, "maxLength": 2},
            "accountStatus": {"type": "string", "enum": ["active", "paused", "closed"]},
            "spendLimit": {"type": "number", "minimum": 0, "maximum": 10000},
        },
    }


def _booking_order_openapi() -> dict[str, Any]:
    return {
        "openapi": "3.1.0",
        "info": {"title": "Booking order API", "version": "1.0.0"},
        "paths": {
            "/booking-orders": {
                "post": {
                    "operationId": "createBookingOrder",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": [
                                        "guestFullName",
                                        "contactEmail",
                                        "contactPhone",
                                        "bookingDate",
                                        "roomQuantity",
                                        "totalAmount",
                                        "currency",
                                        "orderType",
                                    ],
                                    "properties": {
                                        "guestFullName": {"type": "string", "minLength": 3, "maxLength": 80},
                                        "contactEmail": {"type": "string", "format": "email", "minLength": 5, "maxLength": 120},
                                        "contactPhone": {"type": "string", "minLength": 10, "maxLength": 20},
                                        "bookingDate": {"type": "string", "format": "date", "example": "2026-08-15"},
                                        "roomQuantity": {"type": "integer", "minimum": 1, "maximum": 5},
                                        "totalAmount": {"type": "number", "minimum": 1, "maximum": 7500},
                                        "currency": {"type": "string", "minLength": 3, "maxLength": 3},
                                        "orderType": {"type": "string", "enum": ["hotel", "flight", "package"]},
                                        "billingAddress": {"type": "string", "minLength": 5, "maxLength": 120},
                                        "billingCity": {"type": "string"},
                                        "billingCountryCode": {"type": "string", "minLength": 2, "maxLength": 2},
                                    },
                                }
                            }
                        },
                    },
                }
            }
        },
    }


def _expected_business_types() -> dict[str, FieldExpectations]:
    return {
        "registration_profile_contact_form": {
            "firstName": "first_name",
            "lastName": "last_name",
            "displayName": "full_name",
            "email": "email",
            "password": "password",
            "mobilePhone": "phone_number",
            "dateOfBirth": "date_of_birth",
            "streetAddress": "address_line",
            "city": "city",
            "postalCode": "postal_code",
            "countryCode": "country_code",
            "contactPreference": "enum",
        },
        "checkout_payment_form": {
            "email": "email",
            "billingPhone": "phone_number",
            "cardholderFullName": "full_name",
            "cardNumber": "credit_card_number",
            "cardCvv": "cvv",
            "cardExpiry": "expiry_date",
            "billingAddress": "address_line",
            "billingCity": "city",
            "billingPostalCode": "postal_code",
            "billingCountry": "country",
            "orderQuantity": "quantity",
            "orderTotal": "amount",
            "shippingMethod": "enum",
        },
        "customer_account_json_schema": {
            "customerId": "uuid",
            "emailAddress": "email",
            "password": "password",
            "phoneNumber": "phone_number",
            "firstName": "first_name",
            "lastName": "last_name",
            "dateOfBirth": "date_of_birth",
            "addressLine1": "address_line",
            "city": "city",
            "postalCode": "postal_code",
            "countryCode": "country_code",
            "accountStatus": "enum",
            "spendLimit": "amount",
        },
        "booking_order_openapi": {
            "guestFullName": "full_name",
            "contactEmail": "email",
            "contactPhone": "phone_number",
            "bookingDate": "date",
            "roomQuantity": "quantity",
            "totalAmount": "amount",
            "currency": "currency",
            "orderType": "enum",
            "billingAddress": "address_line",
            "billingCity": "city",
            "billingCountryCode": "country_code",
        },
    }


def _assert_happy_record(contract_name: str, record: dict[str, Any]) -> None:
    checks: dict[str, Callable[[dict[str, Any]], None]] = {
        "registration_profile_contact_form": _assert_registration_record,
        "checkout_payment_form": _assert_checkout_record,
        "customer_account_json_schema": _assert_account_record,
        "booking_order_openapi": _assert_booking_order_record,
    }
    checks[contract_name](record)


def _assert_registration_record(record: dict[str, Any]) -> None:
    assert EMAIL_PATTERN.match(record["email"])
    assert PHONE_PATTERN.match(record["mobilePhone"])
    assert record["password"].startswith("Tdf!")
    assert ISO_DATE_PATTERN.match(record["dateOfBirth"])
    assert len(record["countryCode"]) == 2
    assert record["contactPreference"] in {"email", "sms", "phone"}


def _assert_checkout_record(record: dict[str, Any]) -> None:
    assert EMAIL_PATTERN.match(record["email"])
    assert PHONE_PATTERN.match(record["billingPhone"])
    assert _luhn_valid(record["cardNumber"])
    assert re.fullmatch(r"\d{3,4}", record["cardCvv"])
    assert EXPIRY_PATTERN.match(record["cardExpiry"])
    assert 1 <= record["orderQuantity"] <= 10
    assert 1 <= record["orderTotal"] <= 5000
    assert record["shippingMethod"] in {"standard", "express", "overnight"}


def _assert_account_record(record: dict[str, Any]) -> None:
    assert EMAIL_PATTERN.match(record["emailAddress"])
    assert PHONE_PATTERN.match(record["phoneNumber"])
    assert record["password"].startswith("Tdf!")
    assert ISO_DATE_PATTERN.match(record["dateOfBirth"])
    assert len(record["countryCode"]) == 2
    assert record["accountStatus"] in {"active", "paused", "closed"}
    assert 0 <= record["spendLimit"] <= 10000


def _assert_booking_order_record(record: dict[str, Any]) -> None:
    assert EMAIL_PATTERN.match(record["contactEmail"])
    assert PHONE_PATTERN.match(record["contactPhone"])
    assert ISO_DATE_PATTERN.match(record["bookingDate"])
    assert 1 <= record["roomQuantity"] <= 5
    assert 1 <= record["totalAmount"] <= 7500
    assert len(record["currency"]) == 3
    assert record["orderType"] in {"hotel", "flight", "package"}
    assert len(record["billingCountryCode"]) == 2


def _assert_negative_record(scenario: dict[str, Any], record: dict[str, Any]) -> None:
    scenario_id = scenario["id"]
    if scenario_id == "invalid_email_format":
        assert any(value == "not-an-email" for value in record.values())
    elif scenario_id == "invalid_phone_format":
        assert any(value == "not-a-phone" for value in record.values())
    elif scenario_id == "weak_password":
        assert any(value == "password" for value in record.values())
    elif scenario_id == "missing_required_fields":
        assert scenario["fields"]
        assert not set(scenario["fields"]) & set(record)


def _assert_boundary_record(
    contract: dict[str, Any],
    scenario: dict[str, Any],
    record: dict[str, Any],
) -> None:
    for field_name, override in scenario["fields"].items():
        assert record[field_name] == override["value"]
        field = contract["fields"][field_name]
        constraints = field.get("constraints", {})
        if scenario["id"] == "min_length_boundaries":
            assert len(record[field_name]) == constraints["minLength"]
        elif scenario["id"] == "max_length_boundaries":
            assert len(record[field_name]) == constraints["maxLength"]
        elif scenario["id"] == "numeric_minimum_boundaries":
            assert record[field_name] == constraints["minimum"]
        elif scenario["id"] == "numeric_maximum_boundaries":
            assert record[field_name] == constraints["maximum"]
        elif scenario["id"] == "enum_value_boundaries":
            assert record[field_name] in constraints["values"]
        elif scenario["id"] == "date_boundaries":
            assert ISO_DATE_PATTERN.match(record[field_name])


def _input(
    name: str,
    label: str,
    input_type: str,
    *,
    required: bool = False,
    autocomplete: str = "",
    minlength: int | None = None,
    maxlength: int | None = None,
    validation: dict[str, str] | None = None,
) -> dict[str, Any]:
    validation_attributes = dict(validation or {})
    if minlength is not None:
        validation_attributes["minlength"] = str(minlength)
    if maxlength is not None:
        validation_attributes["maxlength"] = str(maxlength)
    return {
        "tag": "input",
        "inputType": input_type,
        "name": name,
        "label": label,
        "required": required,
        "autocomplete": autocomplete,
        "validationAttributes": validation_attributes,
    }


def _select(name: str, label: str, values: list[str], *, required: bool = False) -> dict[str, Any]:
    return {
        "tag": "select",
        "inputType": "select",
        "name": name,
        "label": label,
        "required": required,
        "options": [{"label": value.title(), "value": value} for value in values],
    }


def _luhn_valid(value: str) -> bool:
    digits = [int(character) for character in value if character.isdigit()]
    checksum = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return bool(digits) and checksum % 10 == 0
