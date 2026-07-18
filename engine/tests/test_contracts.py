from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from testdata_factory_engine import ContractValidationError, load_contract, validate_contract_data


ROOT = Path(__file__).resolve().parents[2]
VALID_CONTRACT = json.loads((ROOT / "examples" / "contracts" / "register.tdf.json").read_text(encoding="utf-8"))
INVALID_CONTRACT = json.loads(
    (ROOT / "examples" / "contracts" / "invalid-missing-fields.tdf.json").read_text(encoding="utf-8")
)


def test_loads_valid_contract() -> None:
    contract = load_contract(ROOT / "examples" / "contracts" / "register.tdf.json")

    assert contract.id == "register"
    assert contract.data["fields"]["email"]["businessType"] == "email"


def test_rejects_invalid_contract() -> None:
    with pytest.raises(ContractValidationError, match="fields") as exc:
        load_contract(ROOT / "examples" / "contracts" / "invalid-missing-fields.tdf.json")

    assert exc.value.result is not None
    assert exc.value.result.status == "invalid"


def test_valid_contract_returns_info_finding() -> None:
    result = validate_contract_data(VALID_CONTRACT)

    assert result.status == "valid"
    assert result.score == 1
    assert result.findings[0].severity == "info"
    assert result.findings[0].field is None
    assert result.findings[0].recommendation


def test_invalid_contract_returns_multiple_error_findings() -> None:
    result = validate_contract_data(INVALID_CONTRACT)

    assert result.status == "invalid"
    assert result.score < 1
    assert len(result.findings) >= 2
    assert {finding.severity for finding in result.findings} == {"error"}
    assert {"fields", "scenarios"}.issubset({finding.field for finding in result.findings})
    assert all(finding.message and finding.recommendation for finding in result.findings)


def test_required_field_without_positive_scenario_coverage_returns_warning() -> None:
    contract = deepcopy(VALID_CONTRACT)
    del contract["scenarios"][0]["fields"]["email"]

    result = validate_contract_data(contract)

    assert result.status == "needs_review"
    assert result.score == 0.9
    assert [(finding.severity, finding.field) for finding in result.findings] == [
        ("info", None),
        ("warning", "email"),
    ]
    assert result.findings[1].recommendation == (
        "Add the field to at least one positive scenario with a valid strategy."
    )


def test_unknown_scenario_field_reference_returns_error() -> None:
    contract = deepcopy(VALID_CONTRACT)
    contract["scenarios"][0]["fields"]["emali"] = {"strategy": "valid_email"}

    result = validate_contract_data(contract)

    assert result.status == "invalid"
    assert result.score == 0.75
    assert [(finding.severity, finding.field) for finding in result.findings] == [
        ("info", None),
        ("error", "scenarios[0].fields.emali"),
    ]
    assert result.findings[1].message == "Scenario 'valid_signup' references unknown field 'emali'."
    assert result.findings[1].recommendation == (
        "Use a field defined in contract.fields or add a matching field definition."
    )


def test_load_contract_rejects_unknown_scenario_field_reference(tmp_path: Path) -> None:
    contract = deepcopy(VALID_CONTRACT)
    contract["scenarios"][0]["fields"]["emali"] = {"strategy": "valid_email"}
    contract_path = tmp_path / "unknown-scenario-field.tdf.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    with pytest.raises(ContractValidationError, match="emali") as exc:
        load_contract(contract_path)

    assert exc.value.result is not None
    assert exc.value.result.status == "invalid"


def test_unknown_dependency_field_reference_returns_error() -> None:
    contract = deepcopy(VALID_CONTRACT)
    contract["fields"]["password"]["dependencies"] = {"matchesField": "passwordConfirmation"}

    result = validate_contract_data(contract)

    assert result.status == "invalid"
    assert ("error", "fields.password.dependencies.matchesField") in [
        (finding.severity, finding.field) for finding in result.findings
    ]
    assert any("unknown dependency field 'passwordConfirmation'" in finding.message for finding in result.findings)
