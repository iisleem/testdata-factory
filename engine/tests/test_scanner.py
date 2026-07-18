from __future__ import annotations

from pathlib import Path

import pytest

from testdata_factory_engine import generate_records, validate_contract_data
from testdata_factory_engine.scanner import (
    ScannerDependencyError,
    ScannerError,
    build_contract_draft,
    controls_from_payload,
    scan_contract_draft,
)


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample_form.html"


def test_builds_valid_contract_draft_from_scanned_controls() -> None:
    controls = controls_from_payload(
        [
            {
                "tag": "input",
                "inputType": "text",
                "selector": "#first-name",
                "id": "first-name",
                "name": "firstName",
                "label": "First name",
                "placeholder": "Jane",
                "autocomplete": "given-name",
                "required": True,
                "aria": {"describedby": "first-help"},
                "validationAttributes": {"minlength": "2", "maxlength": "60"},
            },
            {
                "tag": "input",
                "inputType": "email",
                "selector": "#email",
                "id": "email",
                "name": "email",
                "label": "Work email",
                "placeholder": "jane@example.test",
                "required": True,
                "aria": {"describedby": "email-help"},
            },
            {
                "tag": "input",
                "inputType": "number",
                "selector": "#quantity",
                "id": "quantity",
                "name": "quantity",
                "label": "Quantity",
                "validationAttributes": {"min": "1", "max": "10", "step": "1"},
            },
            {
                "tag": "input",
                "inputType": "url",
                "selector": "#website",
                "id": "website",
                "name": "website",
                "label": "Website URL",
                "required": True,
                "aria": {"label": "Website URL", "required": "true"},
                "validationAttributes": {"pattern": "https://.*"},
            },
            {
                "tag": "select",
                "inputType": "select",
                "selector": "#plan",
                "id": "plan",
                "name": "plan",
                "label": "Plan",
                "required": True,
                "options": [
                    {"label": "Select a plan", "value": "", "disabled": True, "selected": True},
                    {"label": "Basic", "value": "basic"},
                    {"label": "Pro", "value": "pro"},
                ],
            },
            {
                "tag": "textarea",
                "inputType": "textarea",
                "selector": "#notes",
                "id": "notes",
                "name": "notes",
                "label": "Notes",
                "placeholder": "Tell us more",
                "validationAttributes": {"maxlength": "500"},
            },
        ]
    )

    draft = build_contract_draft(
        controls,
        source=FIXTURE.resolve().as_uri(),
        contract_id="Signup Form",
        locale_country="us",
    )

    validation = validate_contract_data(draft)
    assert validation.is_valid, validation.to_dict()
    assert draft["id"] == "signup-form"
    assert draft["locale"] == {"language": "en", "country": "US"}
    assert draft["validation"]["status"] == "needs_review"
    assert set(draft["fields"]) == {"firstName", "email", "quantity", "website", "plan", "notes"}

    first_name = draft["fields"]["firstName"]
    assert first_name["label"] == "First name"
    assert first_name["selector"] == "#first-name"
    assert first_name["businessType"] == "first_name"
    assert first_name["required"] is True
    assert first_name["constraints"]["minLength"] == 2
    assert first_name["constraints"]["maxLength"] == 60

    assert draft["fields"]["email"]["constraints"]["format"] == "email"
    assert draft["fields"]["quantity"]["constraints"] == {"step": 1, "minimum": 1, "maximum": 10}
    assert draft["fields"]["website"]["constraints"] == {"pattern": "https://.*", "format": "uri"}
    assert draft["fields"]["plan"]["constraints"]["values"] == ["basic", "pro"]
    assert draft["fields"]["notes"]["constraints"]["maxLength"] == 500
    assert draft["scenarios"][0]["fields"]["website"]["strategy"] == "valid_url"
    assert controls[0].aria["describedby"] == "first-help"
    assert controls[3].aria == {"label": "Website URL", "required": "true"}


def test_uniquifies_fields_without_names_or_ids() -> None:
    controls = controls_from_payload(
        [
            {"tag": "input", "inputType": "text", "label": "Contact name"},
            {"tag": "input", "inputType": "text", "label": "Contact name"},
        ]
    )

    draft = build_contract_draft(controls, source="https://example.test/contact")

    assert set(draft["fields"]) == {"contactName", "contactName2"}


def test_build_contract_draft_fails_when_structured_validation_is_invalid() -> None:
    controls = controls_from_payload([{"tag": "input", "inputType": "text", "name": "email"}])

    with pytest.raises(ScannerError, match="Generated contract draft is invalid"):
        build_contract_draft(controls, source="https://example.test/signup", locale_country="usa")


def test_scan_contract_draft_reads_static_form_when_browser_is_available() -> None:
    pytest.importorskip("playwright.sync_api")

    try:
        draft = scan_contract_draft(FIXTURE, contract_id="sample-form")
    except ScannerDependencyError as exc:
        pytest.skip(str(exc))

    validation = validate_contract_data(draft)
    assert validation.is_valid, validation.to_dict()
    assert draft["source"]["value"].startswith("file://")
    assert draft["fields"]["firstName"]["required"] is True
    assert draft["fields"]["website"]["label"] == "Website URL"
    assert draft["fields"]["plan"]["constraints"]["values"] == ["basic", "pro"]


def test_scanned_contract_drafts_positive_negative_and_boundary_scenarios() -> None:
    controls = controls_from_payload(
        [
            {
                "tag": "input",
                "inputType": "email",
                "name": "workEmail",
                "label": "Work email",
                "required": True,
                "validationAttributes": {"minlength": "6", "maxlength": "80"},
            },
            {
                "tag": "input",
                "inputType": "tel",
                "name": "mobilePhone",
                "label": "Mobile phone",
                "required": True,
            },
            {
                "tag": "input",
                "inputType": "password",
                "name": "password",
                "label": "Password",
                "required": True,
                "validationAttributes": {"minlength": "12", "maxlength": "72"},
            },
            {
                "tag": "input",
                "inputType": "number",
                "name": "spendLimit",
                "label": "Spend limit",
                "validationAttributes": {"min": "0", "max": "500"},
            },
            {
                "tag": "select",
                "inputType": "select",
                "name": "country",
                "label": "Country",
                "options": [
                    {"label": "United States", "value": "US"},
                    {"label": "Canada", "value": "CA"},
                ],
            },
        ]
    )

    draft = build_contract_draft(controls, source="https://example.test/signup")

    validation = validate_contract_data(draft)
    assert validation.is_valid, validation.to_dict()
    scenarios = {scenario["id"]: scenario for scenario in draft["scenarios"]}
    assert list(scenarios) == [
        "valid_form",
        "invalid_email_format",
        "invalid_phone_format",
        "weak_password",
        "missing_required_fields",
        "xss_payloads",
        "sql_injection_payloads",
        "null_required_fields",
        "empty_string_fields",
        "whitespace_only_fields",
        "below_min_length_fields",
        "over_max_length_fields",
        "min_length_boundaries",
        "max_length_boundaries",
        "numeric_minimum_boundaries",
        "numeric_maximum_boundaries",
        "enum_value_boundaries",
    ]
    assert scenarios["valid_form"]["fields"]["workEmail"]["strategy"] == "valid_email"
    assert scenarios["valid_form"]["fields"]["mobilePhone"]["strategy"] == "valid_phone"
    assert scenarios["valid_form"]["fields"]["password"]["strategy"] == "valid_password"
    assert scenarios["missing_required_fields"]["fields"] == {
        "workEmail": {"strategy": "missing_required"},
        "mobilePhone": {"strategy": "missing_required"},
        "password": {"strategy": "missing_required"},
    }
    assert scenarios["numeric_minimum_boundaries"]["fields"]["spendLimit"]["value"] == 0
    assert scenarios["numeric_maximum_boundaries"]["fields"]["spendLimit"]["value"] == 500
    assert scenarios["enum_value_boundaries"]["fields"]["country"]["value"] == "US"

    happy_record = generate_records(draft, "valid_form", seed="scan-suite")[0]
    invalid_email_record = generate_records(draft, "invalid_email_format", seed="scan-suite")[0]
    weak_password_record = generate_records(draft, "weak_password", seed="scan-suite")[0]
    missing_record = generate_records(draft, "missing_required_fields", seed="scan-suite")[0]

    assert happy_record["workEmail"].endswith("@example.test")
    assert happy_record["mobilePhone"].startswith("+155501")
    assert happy_record["password"].startswith("Tdf!")
    assert invalid_email_record["workEmail"] == "not-an-email"
    assert invalid_email_record["password"].startswith("Tdf!")
    assert weak_password_record["password"] == "password"
    assert "workEmail" not in missing_record
    assert "mobilePhone" not in missing_record
    assert "password" not in missing_record


def test_scanned_contract_drafts_advanced_and_cross_field_scenarios() -> None:
    controls = controls_from_payload(
        [
            {
                "tag": "input",
                "inputType": "email",
                "name": "email",
                "label": "Email",
                "required": True,
                "validationAttributes": {"data-unique": "true"},
            },
            {
                "tag": "input",
                "inputType": "password",
                "name": "password",
                "label": "Password",
                "required": True,
                "validationAttributes": {"minlength": "12", "maxlength": "72"},
            },
            {
                "tag": "input",
                "inputType": "password",
                "name": "confirmPassword",
                "label": "Confirm password",
                "required": True,
                "validationAttributes": {"minlength": "12", "maxlength": "72"},
            },
            {
                "tag": "input",
                "inputType": "date",
                "name": "startDate",
                "label": "Start date",
                "required": True,
            },
            {
                "tag": "input",
                "inputType": "date",
                "name": "endDate",
                "label": "End date",
                "required": True,
            },
            {
                "tag": "input",
                "inputType": "number",
                "name": "minGuests",
                "label": "Minimum guests",
                "validationAttributes": {"min": "1", "max": "5"},
            },
            {
                "tag": "input",
                "inputType": "number",
                "name": "maxGuests",
                "label": "Maximum guests",
                "validationAttributes": {"min": "1", "max": "10"},
            },
            {
                "tag": "textarea",
                "inputType": "textarea",
                "name": "notes",
                "label": "Notes",
                "validationAttributes": {"minlength": "3", "maxlength": "200"},
            },
            {
                "tag": "input",
                "inputType": "checkbox",
                "name": "marketingOptIn",
                "label": "Marketing opt-in",
            },
        ]
    )

    draft = build_contract_draft(controls, source="https://example.test/advanced-signup")

    validation = validate_contract_data(draft)
    assert validation.is_valid, validation.to_dict()
    assert draft["fields"]["email"]["constraints"]["unique"] is True
    assert draft["fields"]["confirmPassword"]["dependencies"] == {"matchesField": "password"}
    assert draft["fields"]["endDate"]["dependencies"] == {"rangeEndFor": "startDate"}
    assert draft["fields"]["maxGuests"]["dependencies"] == {"maxFor": "minGuests"}

    scenarios = {scenario["id"]: scenario for scenario in draft["scenarios"]}
    assert {
        "xss_payloads",
        "sql_injection_payloads",
        "duplicate_unique_fields",
        "boolean_false_boundaries",
        "boolean_true_boundaries",
        "mismatched_confirmation_fields",
        "invalid_date_ranges",
        "invalid_numeric_ranges",
    } <= scenarios.keys()

    happy_record = generate_records(draft, "valid_form", seed="scan-advanced")[0]
    mismatch_record = generate_records(draft, "mismatched_confirmation_fields", seed="scan-advanced")[0]
    invalid_date_record = generate_records(draft, "invalid_date_ranges", seed="scan-advanced")[0]
    invalid_numeric_record = generate_records(draft, "invalid_numeric_ranges", seed="scan-advanced")[0]
    duplicate_records = generate_records(draft, "duplicate_unique_fields", count=2, seed="scan-advanced")
    xss_record = generate_records(draft, "xss_payloads", seed="scan-advanced")[0]

    assert happy_record["confirmPassword"] == happy_record["password"]
    assert happy_record["endDate"] > happy_record["startDate"]
    assert happy_record["maxGuests"] >= happy_record["minGuests"]
    assert mismatch_record["confirmPassword"] != mismatch_record["password"]
    assert invalid_date_record["endDate"] < invalid_date_record["startDate"]
    assert invalid_numeric_record["maxGuests"] < invalid_numeric_record["minGuests"]
    assert duplicate_records[0]["email"] == duplicate_records[1]["email"]
    assert xss_record["notes"] == "<script>alert('tdf')</script>"
