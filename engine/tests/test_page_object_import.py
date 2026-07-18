from __future__ import annotations

import json
from pathlib import Path

import pytest

from testdata_factory_engine import generate_records, validate_contract_data
from testdata_factory_engine.cli import main
from testdata_factory_engine.page_object_import import (
    PageObjectImportError,
    import_page_object_file,
    parse_page_object_controls,
)


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "page_objects"


def test_imports_java_page_object_fields_and_generated_scenarios() -> None:
    contract = import_page_object_file(
        FIXTURES / "RegisterPage.java",
        contract_id="register-page",
        locale={"language": "en", "country": "US"},
    )

    validation = validate_contract_data(contract)
    assert validation.is_valid, validation.to_dict()
    assert contract["id"] == "register-page"
    assert contract["source"]["type"] == "page_object"
    assert contract["locale"] == {"language": "en", "country": "US"}
    assert set(contract["fields"]) == {"email", "password", "mobilePhone", "spendLimit", "website"}

    fields = contract["fields"]
    assert fields["email"]["businessType"] == "email"
    assert fields["email"]["required"] is True
    assert fields["email"]["selector"] == "input[type='email'][name='email'][required]"
    assert fields["email"]["inference"]["signals"][:2] == ["page_object:java", "page_object:find_by"]
    assert fields["password"]["businessType"] == "password"
    assert fields["password"]["constraints"]["minLength"] == 12
    assert fields["password"]["constraints"]["maxLength"] == 72
    assert fields["mobilePhone"]["businessType"] == "phone_number"
    assert fields["spendLimit"]["businessType"] == "amount"
    assert fields["spendLimit"]["constraints"] == {"minimum": 0, "maximum": 500}
    assert fields["website"]["businessType"] == "url"

    scenarios = {scenario["id"]: scenario for scenario in contract["scenarios"]}
    assert scenarios["valid_page_object"]["fields"]["email"]["strategy"] == "valid_email"
    assert scenarios["valid_page_object"]["fields"]["password"]["strategy"] == "valid_password"
    assert scenarios["valid_page_object"]["fields"]["mobilePhone"]["strategy"] == "valid_phone"
    assert scenarios["valid_page_object"]["fields"]["spendLimit"]["strategy"] == "valid_decimal"
    assert scenarios["valid_page_object"]["fields"]["website"]["strategy"] == "valid_url"
    assert scenarios["invalid_email_format"]["fields"] == {"email": {"strategy": "invalid_email_format"}}
    assert scenarios["invalid_phone_format"]["fields"] == {"mobilePhone": {"strategy": "invalid_phone_format"}}
    assert scenarios["weak_password"]["fields"] == {"password": {"strategy": "weak_password"}}
    assert scenarios["missing_required_fields"]["fields"] == {"email": {"strategy": "missing_required"}}
    assert scenarios["numeric_minimum_boundaries"]["fields"]["spendLimit"]["value"] == 0
    assert scenarios["numeric_maximum_boundaries"]["fields"]["spendLimit"]["value"] == 500

    happy_record = generate_records(contract, "valid_page_object", seed="page-object-suite")[0]
    invalid_email_record = generate_records(contract, "invalid_email_format", seed="page-object-suite")[0]
    weak_password_record = generate_records(contract, "weak_password", seed="page-object-suite")[0]
    missing_record = generate_records(contract, "missing_required_fields", seed="page-object-suite")[0]

    assert happy_record["email"].endswith("@example.test")
    assert happy_record["password"].startswith("Tdf!")
    assert happy_record["mobilePhone"].startswith("+155501")
    assert 0 <= happy_record["spendLimit"] <= 500
    assert happy_record["website"].startswith("https://")
    assert invalid_email_record["email"] == "not-an-email"
    assert weak_password_record["password"] == "password"
    assert "email" not in missing_record


@pytest.mark.parametrize(
    ("filename", "language"),
    [
        ("RegisterPage.java", "java"),
        ("register.page.ts", "typescript"),
        ("register_page.py", "python"),
    ],
)
def test_parser_covers_java_typescript_and_python_page_objects(filename: str, language: str) -> None:
    contract = import_page_object_file(FIXTURES / filename, contract_id=f"{language}-register-page")

    validation = validate_contract_data(contract)
    assert validation.is_valid, validation.to_dict()
    assert contract["source"]["type"] == "page_object"
    assert {"email", "password", "mobilePhone", "spendLimit", "website"}.issubset(contract["fields"])
    assert contract["fields"]["email"]["businessType"] == "email"
    assert contract["fields"]["password"]["businessType"] == "password"
    assert contract["fields"]["mobilePhone"]["businessType"] == "phone_number"
    assert contract["fields"]["spendLimit"]["businessType"] == "amount"
    assert contract["fields"]["website"]["businessType"] == "url"
    assert any(
        signal == f"page_object:{language}"
        for field in contract["fields"].values()
        for signal in field["inference"]["signals"]
    )


def test_import_page_object_cli_writes_contract(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "register-page.tdf.json"

    exit_code = main(
        [
            "import",
            "page-object",
            str(FIXTURES / "register.page.ts"),
            "--id",
            "register-page-ts",
            "--out",
            str(output),
        ]
    )

    assert exit_code == 0
    assert "Imported contract: register-page-ts" in capsys.readouterr().out
    contract = json.loads(output.read_text(encoding="utf-8"))
    assert contract["id"] == "register-page-ts"
    assert contract["source"]["type"] == "page_object"
    assert contract["fields"]["email"]["businessType"] == "email"
    assert contract["scenarios"][0]["id"] == "valid_page_object"


def test_scan_page_object_cli_writes_contract(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "register-page.tdf.json"

    exit_code = main(
        [
            "scan",
            "--page-object",
            str(FIXTURES / "register_page.py"),
            "--id",
            "register-page-py",
            "--out",
            str(output),
        ]
    )

    assert exit_code == 0
    assert "Wrote contract: register-page-py" in capsys.readouterr().out
    contract = json.loads(output.read_text(encoding="utf-8"))
    validation = validate_contract_data(contract)
    assert validation.is_valid, validation.to_dict()
    assert contract["source"]["type"] == "page_object"
    assert contract["fields"]["website"]["selector"] == 'input[type="url"][name="website"]'
    assert contract["scenarios"][0]["fields"]["website"]["strategy"] == "valid_url"


def test_rejects_page_object_without_supported_controls() -> None:
    with pytest.raises(PageObjectImportError, match="No supported page object controls"):
        parse_page_object_controls("public class EmptyPage {}", language="java")
