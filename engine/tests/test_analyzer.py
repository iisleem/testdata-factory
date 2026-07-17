from __future__ import annotations

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
