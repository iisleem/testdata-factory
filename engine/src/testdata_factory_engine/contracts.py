from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


FindingSeverity = Literal["info", "warning", "error"]
ValidationStatus = Literal["valid", "needs_review", "invalid"]


@dataclass(frozen=True)
class ValidationFinding:
    severity: FindingSeverity
    field: str | None
    message: str
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "field": self.field,
            "message": self.message,
            "recommendation": self.recommendation,
        }


@dataclass(frozen=True)
class ValidationResult:
    status: ValidationStatus
    score: float
    findings: tuple[ValidationFinding, ...]

    @property
    def is_valid(self) -> bool:
        return self.status != "invalid"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "score": self.score,
            "findings": [finding.to_dict() for finding in self.findings],
        }


class ContractValidationError(ValueError):
    """Raised when a contract does not match the TestData Factory schema."""

    def __init__(self, message: str, result: ValidationResult | None = None) -> None:
        super().__init__(message)
        self.result = result


@dataclass(frozen=True)
class Contract:
    path: Path
    data: dict[str, Any]

    @property
    def id(self) -> str:
        return str(self.data["id"])


def default_schema_path() -> Path:
    return Path(__file__).resolve().parents[3] / "specs" / "contract-schema" / "tdf-contract.schema.json"


def load_json(path: str | Path) -> dict[str, Any]:
    resolved = Path(path)
    with resolved.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ContractValidationError(f"Expected JSON object in {resolved}")
    return data


def load_schema(schema_path: str | Path | None = None) -> dict[str, Any]:
    return load_json(schema_path or default_schema_path())


def validate_contract_data(data: dict[str, Any], schema: dict[str, Any] | None = None) -> ValidationResult:
    validator = Draft202012Validator(schema or load_schema())
    errors = sorted(validator.iter_errors(data), key=lambda error: list(error.path))
    findings = _schema_findings(errors)
    has_schema_findings = bool(findings)
    if not findings:
        findings.append(
            ValidationFinding(
                severity="info",
                field=None,
                message="Contract matches the schema.",
                recommendation="Keep this contract under version control with the tests that use it.",
            )
        )
    findings.extend(_scenario_field_reference_findings(data))
    if not has_schema_findings:
        findings.extend(_scenario_coverage_findings(data))
    return _result_from_findings(findings)


def validate_contract_file(path: str | Path, schema_path: str | Path | None = None) -> ValidationResult:
    return validate_contract_data(load_json(path), load_schema(schema_path))


def load_contract(path: str | Path, schema_path: str | Path | None = None) -> Contract:
    resolved = Path(path)
    data = load_json(resolved)
    result = validate_contract_data(data, load_schema(schema_path))
    if not result.is_valid:
        raise ContractValidationError(_format_validation_result(result), result)
    return Contract(path=resolved, data=data)


def _format_validation_error(error: ValidationError) -> str:
    location = ".".join(str(part) for part in error.absolute_path)
    if not location:
        location = "<root>"
    return f"{location}: {error.message}"


def _format_validation_result(result: ValidationResult) -> str:
    errors = [finding for finding in result.findings if finding.severity == "error"]
    if not errors:
        return f"Contract validation status: {result.status}"
    return "; ".join(_format_finding(finding) for finding in errors)


def _format_finding(finding: ValidationFinding) -> str:
    location = finding.field or "<root>"
    return f"{location}: {finding.message}"


def _schema_findings(errors: list[ValidationError]) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    seen: set[tuple[str, str | None, str]] = set()
    for error in errors:
        for finding in _findings_for_schema_error(error):
            key = (finding.severity, finding.field, finding.message)
            if key not in seen:
                findings.append(finding)
                seen.add(key)
    return findings


def _findings_for_schema_error(error: ValidationError) -> list[ValidationFinding]:
    if error.validator == "required" and isinstance(error.instance, dict) and isinstance(error.validator_value, list):
        missing_fields = sorted(set(error.validator_value) - set(error.instance))
        if missing_fields:
            return [
                ValidationFinding(
                    severity="error",
                    field=_join_path(error.absolute_path, missing_field),
                    message=f"Required property '{missing_field}' is missing.",
                    recommendation="Add the required property to the contract.",
                )
                for missing_field in missing_fields
            ]

    return [
        ValidationFinding(
            severity="error",
            field=_field_from_error(error),
            message=error.message,
            recommendation=_schema_recommendation(error),
        )
    ]


def _field_from_error(error: ValidationError) -> str | None:
    path = ".".join(str(part) for part in error.absolute_path)
    return path or None


def _join_path(path: Any, field: str) -> str:
    parts = [str(part) for part in path]
    parts.append(field)
    return ".".join(parts)


def _schema_recommendation(error: ValidationError) -> str:
    if error.validator == "additionalProperties":
        return "Remove unsupported properties or update the contract schema."
    if error.validator == "enum":
        allowed = ", ".join(str(value) for value in error.validator_value)
        return f"Use one of the supported values: {allowed}."
    if error.validator in {"minItems", "minLength", "minProperties", "minimum"}:
        return "Increase the value so it satisfies the schema minimum."
    if error.validator in {"maxLength", "maximum"}:
        return "Reduce the value so it satisfies the schema maximum."
    if error.validator == "type":
        return "Use a value that matches the expected contract type."
    return "Update the contract to satisfy the schema rule."


def _scenario_coverage_findings(data: dict[str, Any]) -> list[ValidationFinding]:
    fields = data.get("fields", {})
    scenarios = data.get("scenarios", [])
    if not isinstance(fields, dict) or not isinstance(scenarios, list):
        return []

    positive_scenarios = [
        scenario for scenario in scenarios if isinstance(scenario, dict) and scenario.get("kind") == "positive"
    ]
    findings: list[ValidationFinding] = []
    for field_name, field in fields.items():
        if not isinstance(field, dict) or field.get("required") is not True:
            continue
        if not _is_required_field_covered(field_name, positive_scenarios):
            findings.append(
                ValidationFinding(
                    severity="warning",
                    field=str(field_name),
                    message="Required field is not covered by a positive scenario.",
                    recommendation="Add the field to at least one positive scenario with a valid strategy.",
                )
            )
    return findings


def _scenario_field_reference_findings(data: dict[str, Any]) -> list[ValidationFinding]:
    fields = data.get("fields", {})
    scenarios = data.get("scenarios", [])
    if not isinstance(fields, dict) or not isinstance(scenarios, list):
        return []

    known_fields = set(fields)
    findings: list[ValidationFinding] = []
    for scenario_index, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict):
            continue
        scenario_fields = scenario.get("fields", {})
        if not isinstance(scenario_fields, dict):
            continue
        scenario_name = str(scenario.get("id") or scenario_index)
        for field_name in scenario_fields:
            if field_name not in known_fields:
                findings.append(
                    ValidationFinding(
                        severity="error",
                        field=f"scenarios[{scenario_index}].fields.{field_name}",
                        message=f"Scenario '{scenario_name}' references unknown field '{field_name}'.",
                        recommendation="Use a field defined in contract.fields or add a matching field definition.",
                    )
                )
    return findings


def _is_required_field_covered(field_name: str, scenarios: list[dict[str, Any]]) -> bool:
    for scenario in scenarios:
        scenario_fields = scenario.get("fields", {})
        if not isinstance(scenario_fields, dict) or field_name not in scenario_fields:
            continue
        field_strategy = scenario_fields[field_name]
        if not isinstance(field_strategy, dict):
            continue
        if field_strategy.get("strategy") not in {"missing", "missing_required"}:
            return True
    return False


def _result_from_findings(findings: list[ValidationFinding]) -> ValidationResult:
    error_count = sum(1 for finding in findings if finding.severity == "error")
    warning_count = sum(1 for finding in findings if finding.severity == "warning")
    if error_count:
        status: ValidationStatus = "invalid"
    elif warning_count:
        status = "needs_review"
    else:
        status = "valid"
    score = max(0.0, 1.0 - (error_count * 0.25) - (warning_count * 0.1))
    return ValidationResult(status=status, score=round(score, 2), findings=tuple(findings))
