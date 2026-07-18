from __future__ import annotations

import pytest

from testdata_factory_engine import FieldCandidate, infer_field
from testdata_factory_engine.analyzer import annotate_cross_field_dependencies, draft_scenarios


def test_infers_email_from_input_type() -> None:
    field = infer_field(FieldCandidate(name="contact", input_type="email", required=True))

    assert field["businessType"] == "email"
    assert field["dataType"] == "string"
    assert field["required"] is True
    assert field["constraints"]["format"] == "email"
    assert field["inference"]["confidence"] >= 0.9


def test_infers_phone_from_label() -> None:
    field = infer_field(FieldCandidate(label="Mobile phone", input_type="text"))

    assert field["businessType"] == "phone_number"
    assert field["inference"]["signals"][0].startswith("text:")


def test_infers_password_from_input_type() -> None:
    field = infer_field(FieldCandidate(name="secret", input_type="password"))

    assert field["businessType"] == "password"


def test_infers_name_from_autocomplete() -> None:
    field = infer_field(FieldCandidate(name="first", autocomplete="given-name"))

    assert field["businessType"] == "first_name"


def test_infers_enum_from_options() -> None:
    field = infer_field(FieldCandidate(name="plan", options=["basic", "pro"]))

    assert field["businessType"] == "enum"
    assert field["dataType"] == "enum"
    assert field["constraints"]["values"] == ["basic", "pro"]


def test_infers_boolean_from_checkbox() -> None:
    field = infer_field(FieldCandidate(name="newsletter", input_type="checkbox"))

    assert field["businessType"] == "boolean"
    assert field["dataType"] == "boolean"


def test_infers_date_of_birth() -> None:
    field = infer_field(FieldCandidate(label="Date of birth", input_type="date"))

    assert field["businessType"] == "date_of_birth"
    assert field["constraints"]["format"] == "date"


def test_infers_amount_from_label() -> None:
    field = infer_field(FieldCandidate(label="Total amount", input_type="number"))

    assert field["businessType"] == "amount"
    assert field["dataType"] == "decimal"


def test_falls_back_to_low_confidence_free_text() -> None:
    field = infer_field(FieldCandidate(name="comments"))

    assert field["businessType"] == "free_text"
    assert field["inference"]["confidence"] < 0.5


@pytest.mark.parametrize(
    ("candidate", "business_type"),
    [
        (FieldCandidate(label="First name"), "first_name"),
        (FieldCandidate(placeholder="Last Name"), "last_name"),
        (FieldCandidate(name="full_name"), "full_name"),
        (FieldCandidate(label="Username"), "username"),
        (FieldCandidate(name="emailAddress"), "email"),
        (FieldCandidate(label="Cell phone"), "phone_number"),
        (FieldCandidate(label="Tel", input_type="tel"), "phone_number"),
        (FieldCandidate(label="Confirm password"), "password"),
        (FieldCandidate(label="Address line 1"), "address_line"),
        (FieldCandidate(name="city"), "city"),
        (FieldCandidate(label="State / Province"), "state"),
        (FieldCandidate(label="ZIP / Postal code"), "postal_code"),
        (FieldCandidate(name="countryCode"), "country_code"),
        (FieldCandidate(label="Country code"), "country_code"),
        (FieldCandidate(name="shippingCountry", autocomplete="country"), "country_code"),
        (FieldCandidate(name="shippingCountry", autocomplete="country-name"), "country"),
        (FieldCandidate(name="country"), "country"),
        (FieldCandidate(label="DOB"), "date_of_birth"),
        (FieldCandidate(label="Website URL"), "url"),
        (FieldCandidate(label="Domain"), "domain"),
        (FieldCandidate(label="External profile ID"), "uuid"),
        (FieldCandidate(label="Spend limit"), "amount"),
        (FieldCandidate(label="Quantity count", input_type="number"), "quantity"),
        (FieldCandidate(label="Tax rate"), "percentage"),
        (FieldCandidate(label="Currency"), "currency"),
        (FieldCandidate(label="Account number"), "account_number"),
        (FieldCandidate(label="IBAN"), "iban"),
        (FieldCandidate(label="Credit card number"), "credit_card_number"),
        (FieldCandidate(label="CVV security code"), "cvv"),
        (FieldCandidate(label="Card expiry date"), "expiry_date"),
        (FieldCandidate(label="Verification code"), "otp"),
        (FieldCandidate(label="Tax ID"), "tax_id"),
        (FieldCandidate(label="National ID"), "national_id"),
        (FieldCandidate(label="Passport number"), "passport_number"),
        (FieldCandidate(label="Accept terms and consent", input_type="checkbox"), "boolean"),
        (FieldCandidate(label="Newsletter opt-in", input_type="checkbox"), "boolean"),
    ],
)
def test_infers_realistic_automation_field_variants(candidate: FieldCandidate, business_type: str) -> None:
    assert infer_field(candidate)["businessType"] == business_type


def test_drafts_security_robustness_and_cross_field_scenarios() -> None:
    fields = annotate_cross_field_dependencies(
        {
            "email": _field("string", "email", required=True, constraints={"format": "email", "unique": True}),
            "password": _field("string", "password", required=True, constraints={"minLength": 12, "maxLength": 72}),
            "confirmPassword": _field(
                "string",
                "password",
                required=True,
                label="Confirm password",
                constraints={"minLength": 12, "maxLength": 72},
            ),
            "startDate": _field("date", "date", required=True, label="Start date"),
            "endDate": _field("date", "date", required=True, label="End date"),
            "minGuests": _field("integer", "integer", required=True, label="Minimum guests"),
            "maxGuests": _field("integer", "integer", required=True, label="Maximum guests"),
            "notes": _field("string", "free_text", constraints={"minLength": 3, "maxLength": 40}),
            "marketingOptIn": _field("boolean", "boolean"),
        }
    )

    assert fields["confirmPassword"]["dependencies"] == {"matchesField": "password"}
    assert fields["startDate"]["dependencies"] == {"rangeStartFor": "endDate"}
    assert fields["endDate"]["dependencies"] == {"rangeEndFor": "startDate"}
    assert fields["minGuests"]["dependencies"] == {"minFor": "maxGuests"}
    assert fields["maxGuests"]["dependencies"] == {"maxFor": "minGuests"}

    scenarios = {
        scenario["id"]: scenario
        for scenario in draft_scenarios(
            fields,
            positive_id="valid_payload",
            positive_description="All fields contain valid values.",
        )
    }

    assert {
        "xss_payloads",
        "sql_injection_payloads",
        "null_required_fields",
        "empty_string_fields",
        "whitespace_only_fields",
        "below_min_length_fields",
        "over_max_length_fields",
        "duplicate_unique_fields",
        "boolean_false_boundaries",
        "boolean_true_boundaries",
        "matching_confirmation_fields",
        "mismatched_confirmation_fields",
        "valid_date_ranges",
        "invalid_date_ranges",
        "valid_numeric_ranges",
        "invalid_numeric_ranges",
    } <= scenarios.keys()
    assert scenarios["valid_payload"]["fields"]["confirmPassword"]["strategy"] == "match_field"
    assert scenarios["valid_payload"]["fields"]["endDate"]["strategy"] == "range_end_after_start"
    assert scenarios["valid_payload"]["fields"]["maxGuests"]["strategy"] == "numeric_max_at_or_above_min"
    assert scenarios["duplicate_unique_fields"]["fields"] == {"email": {"strategy": "duplicate_value"}}
    assert scenarios["mismatched_confirmation_fields"]["fields"] == {"confirmPassword": {"strategy": "mismatch_field"}}
    assert scenarios["invalid_date_ranges"]["fields"] == {"endDate": {"strategy": "date_before_related_field"}}
    assert scenarios["invalid_numeric_ranges"]["fields"] == {"maxGuests": {"strategy": "numeric_max_below_min"}}


def _field(
    data_type: str,
    business_type: str,
    *,
    required: bool = False,
    label: str = "",
    constraints: dict | None = None,
) -> dict:
    field = {
        "dataType": data_type,
        "businessType": business_type,
        "required": required,
        "inference": {
            "confidence": 1,
            "signals": ["test"],
        },
    }
    if label:
        field["label"] = label
    if constraints:
        field["constraints"] = constraints
    return field
