from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from testdata_factory_engine import cli, validate_contract_data
from testdata_factory_engine.cli import main
from testdata_factory_engine.scanner import build_contract_draft, controls_from_payload


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "examples" / "contracts" / "register.tdf.json"
INVALID_CONTRACT = ROOT / "examples" / "contracts" / "invalid-missing-fields.tdf.json"
VALID_CONTRACT = json.loads(CONTRACT.read_text(encoding="utf-8"))
FIXTURES = ROOT / "engine" / "tests" / "fixtures"


def test_help_lists_commands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])

    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "validate" in output
    assert "import" in output
    assert "generate" in output
    assert "scan" in output
    assert "scan-url" in output
    assert "models" in output


def test_scan_help_lists_sources(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["scan", "--help"])

    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "--url" in output
    assert "--json-schema" in output
    assert "--openapi" in output
    assert "--operation" in output
    assert "--out" in output


def test_validate_contract(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["validate", str(CONTRACT)])

    assert exit_code == 0
    assert "Valid contract: register" in capsys.readouterr().out


def test_validate_contract_outputs_structured_json(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["validate", "--json", str(CONTRACT)])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "valid"
    assert output["score"] == 1
    assert output["findings"][0]["severity"] == "info"


def test_validate_invalid_contract_outputs_all_findings(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["validate", "--json", str(INVALID_CONTRACT)])

    assert exit_code == 1
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "invalid"
    assert len(output["findings"]) >= 2
    assert {"fields", "scenarios"}.issubset({finding["field"] for finding in output["findings"]})


def test_validate_contract_reports_unknown_scenario_field_json(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    contract = deepcopy(VALID_CONTRACT)
    contract["scenarios"][0]["fields"]["emali"] = {"strategy": "valid_email"}
    contract_path = tmp_path / "unknown-scenario-field.tdf.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    exit_code = main(["validate", "--json", str(contract_path)])

    assert exit_code == 1
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "invalid"
    assert output["findings"][1] == {
        "severity": "error",
        "field": "scenarios[0].fields.emali",
        "message": "Scenario 'valid_signup' references unknown field 'emali'.",
        "recommendation": "Use a field defined in contract.fields or add a matching field definition.",
    }


def test_generate_contract_data(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["generate", "--contract", str(CONTRACT), "--scenario", "valid_signup", "--count", "1", "--seed", "cli"])

    assert exit_code == 0
    records = json.loads(capsys.readouterr().out)
    assert len(records) == 1
    assert records[0]["email"].endswith("@example.test")


def test_import_json_schema_writes_contract(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "customer.tdf.json"

    exit_code = main(
        [
            "import",
            "json-schema",
            str(FIXTURES / "customer.schema.json"),
            "--id",
            "customer-signup",
            "--out",
            str(output),
        ]
    )

    assert exit_code == 0
    assert "Imported contract: customer-signup" in capsys.readouterr().out
    contract = json.loads(output.read_text(encoding="utf-8"))
    assert contract["id"] == "customer-signup"
    assert contract["fields"]["plan"]["constraints"]["values"] == ["basic", "pro", "enterprise"]


def test_import_json_schema_defaults_id_to_schema_title(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "customer.tdf.json"

    exit_code = main(
        [
            "import",
            "json-schema",
            str(FIXTURES / "customer.schema.json"),
            "--out",
            str(output),
        ]
    )

    assert exit_code == 0
    assert "Imported contract: customer-signup" in capsys.readouterr().out
    contract = json.loads(output.read_text(encoding="utf-8"))
    assert contract["id"] == "customer-signup"


def test_import_openapi_writes_selected_operation_contract(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "create-customer.tdf.json"

    exit_code = main(
        [
            "import",
            "openapi",
            str(FIXTURES / "customer.openapi.json"),
            "--operation",
            "createCustomer",
            "--out",
            str(output),
        ]
    )

    assert exit_code == 0
    assert "Imported contract: create-customer" in capsys.readouterr().out
    contract = json.loads(output.read_text(encoding="utf-8"))
    assert contract["source"]["type"] == "openapi"
    assert contract["fields"]["email"]["required"] is True
    assert contract["fields"]["role"]["constraints"]["values"] == ["admin", "member"]


def test_scan_json_schema_writes_valid_contract(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "customer.tdf.json"

    exit_code = main(
        [
            "scan",
            "--json-schema",
            str(FIXTURES / "customer.schema.json"),
            "--id",
            "customer-signup",
            "--out",
            str(output),
        ]
    )

    assert exit_code == 0
    assert "Wrote contract: customer-signup" in capsys.readouterr().out
    contract = json.loads(output.read_text(encoding="utf-8"))
    validate_contract_data(contract)
    assert contract["source"]["type"] == "json_schema"
    assert contract["fields"]["email"]["businessType"] == "email"


def test_scan_openapi_writes_selected_operation_contract(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "create-customer.tdf.json"

    exit_code = main(
        [
            "scan",
            "--openapi",
            str(FIXTURES / "customer.openapi.json"),
            "--operation",
            "createCustomer",
            "--out",
            str(output),
        ]
    )

    assert exit_code == 0
    assert "Wrote contract: create-customer" in capsys.readouterr().out
    contract = json.loads(output.read_text(encoding="utf-8"))
    validate_contract_data(contract)
    assert contract["source"]["type"] == "openapi"
    assert contract["fields"]["role"]["constraints"]["values"] == ["admin", "member"]


def test_scan_url_writes_valid_contract_from_fixture(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "sample-form.tdf.json"

    def scan_fixture(
        source: str,
        *,
        contract_id: str | None = None,
        locale_language: str = "en",
        locale_country: str | None = None,
    ) -> dict:
        controls = controls_from_payload(
            [
                {
                    "tag": "input",
                    "inputType": "email",
                    "selector": "#email",
                    "id": "email",
                    "name": "email",
                    "label": "Work email",
                    "required": True,
                }
            ]
        )
        return build_contract_draft(
            controls,
            source=source,
            contract_id=contract_id,
            locale_language=locale_language,
            locale_country=locale_country,
        )

    monkeypatch.setattr(cli, "scan_contract_draft", scan_fixture)

    exit_code = main(
        [
            "scan",
            "--url",
            str(FIXTURES / "sample_form.html"),
            "--id",
            "sample-form",
            "--out",
            str(output),
            "--country",
            "us",
        ]
    )

    assert exit_code == 0
    assert "Wrote contract: sample-form" in capsys.readouterr().out
    contract = json.loads(output.read_text(encoding="utf-8"))
    validate_contract_data(contract)
    assert contract["locale"] == {"language": "en", "country": "US"}
    assert contract["fields"]["email"]["required"] is True


def test_scan_openapi_missing_operation_reports_readable_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "create-customer.tdf.json"

    exit_code = main(["scan", "--openapi", str(FIXTURES / "customer.openapi.json"), "--out", str(output)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "error: --operation is required with --openapi" in captured.err
    assert not output.exists()


def test_models_doctor_outputs_profiles(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["models", "doctor"])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert set(output["profiles"]) == {"light", "balanced", "strong"}
