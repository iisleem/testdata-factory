from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from testdata_factory_engine.cli import main


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
    assert "scan-url" in output
    assert "models" in output


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


def test_models_doctor_outputs_profiles(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["models", "doctor"])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert set(output["profiles"]) == {"light", "balanced", "strong"}
