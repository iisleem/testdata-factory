from __future__ import annotations

import pytest

from testdata_factory_engine import FieldCandidate, infer_field


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
