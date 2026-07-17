from __future__ import annotations

from pathlib import Path

import pytest

from testdata_factory_engine import validate_contract_data
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

    validate_contract_data(draft)
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

    validate_contract_data(draft)
    assert draft["source"]["value"].startswith("file://")
    assert draft["fields"]["firstName"]["required"] is True
    assert draft["fields"]["website"]["label"] == "Website URL"
    assert draft["fields"]["plan"]["constraints"]["values"] == ["basic", "pro"]
