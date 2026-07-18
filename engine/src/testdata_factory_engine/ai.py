from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal

from .contracts import (
    Contract,
    ValidationFinding,
    ValidationResult,
    validate_contract_data,
)
from .models import LocalModelProvider, ModelProviderError, get_model_profile


AIWorkflowMode = Literal["scenario_plan"]
VALIDATION_STATUSES = {"valid", "needs_review", "invalid"}
FINDING_SEVERITIES = {"info", "warning", "error"}


class AIWorkflowError(RuntimeError):
    """Raised when an explicit local AI workflow cannot complete."""


@dataclass(frozen=True)
class AIScenarioAssistResult:
    mode: AIWorkflowMode
    model_profile: str
    provider_type: str
    model: str
    proposal: dict[str, Any]
    validation: ValidationResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "modelProfile": self.model_profile,
            "provider": {
                "type": self.provider_type,
                "model": self.model,
            },
            "proposal": self.proposal,
            "validation": self.validation.to_dict(),
        }


def draft_scenarios_with_validation(
    contract: Contract | dict[str, Any],
    provider: LocalModelProvider,
    *,
    model_profile: str = "balanced",
    goal: str | None = None,
) -> AIScenarioAssistResult:
    """Run generator and validator agents to propose contract scenario additions."""

    get_model_profile(model_profile)
    contract_data = contract.data if isinstance(contract, Contract) else contract
    contract_result = validate_contract_data(contract_data)
    if not contract_result.is_valid:
        raise AIWorkflowError(f"AI scenario assist requires a valid contract: {_validation_summary(contract_result)}")

    generator_response = _chat_json(
        provider,
        _generator_messages(contract_data, goal=goal),
        SCENARIO_PROPOSAL_SCHEMA,
        agent_name="Generator agent",
    )
    proposal = _scenario_proposal_from_response(generator_response)
    local_result = validate_scenario_proposal(contract_data, proposal)

    validator_response = _chat_json(
        provider,
        _validator_messages(contract_data, proposal, local_result),
        VALIDATION_REVIEW_SCHEMA,
        agent_name="Validator agent",
    )
    validation = _merge_validation_results(
        _validation_result_from_response(validator_response, agent_name="Validator agent"),
        local_result,
    )

    return AIScenarioAssistResult(
        mode="scenario_plan",
        model_profile=model_profile,
        provider_type=provider.provider_type,
        model=provider.model,
        proposal=proposal,
        validation=validation,
    )


def validate_scenario_proposal(contract: Contract | dict[str, Any], proposal: dict[str, Any]) -> ValidationResult:
    contract_data = contract.data if isinstance(contract, Contract) else contract
    scenarios = proposal.get("scenarios")
    if not isinstance(scenarios, list):
        raise AIWorkflowError("Generator agent response must include proposal.scenarios as an array.")

    findings = _duplicate_scenario_findings(contract_data, scenarios)
    candidate_contract = deepcopy(contract_data)
    existing_scenarios = candidate_contract.get("scenarios", [])
    if not isinstance(existing_scenarios, list):
        existing_scenarios = []
    existing_count = len(existing_scenarios)
    candidate_contract["scenarios"] = [*existing_scenarios, *scenarios]

    candidate_result = validate_contract_data(candidate_contract)
    for finding in candidate_result.findings:
        if finding.severity == "info":
            continue
        findings.append(
            ValidationFinding(
                severity=finding.severity,
                field=_proposal_field(finding.field, existing_count),
                message=finding.message,
                recommendation=finding.recommendation,
            )
        )

    if not findings:
        findings.append(
            ValidationFinding(
                severity="info",
                field="proposal.scenarios",
                message="Scenario proposal is structurally compatible with the contract.",
                recommendation="Review the proposal, then copy approved scenarios into contract.scenarios.",
            )
        )
    return _result_from_findings(findings)


def _chat_json(
    provider: LocalModelProvider,
    messages: list[dict[str, str]],
    response_schema: dict[str, Any],
    *,
    agent_name: str,
) -> dict[str, Any]:
    try:
        return provider.chat_json(messages, response_schema)
    except ModelProviderError as exc:
        raise AIWorkflowError(f"{agent_name} failed: {exc}") from exc


def _generator_messages(contract: dict[str, Any], *, goal: str | None) -> list[dict[str, str]]:
    requested_goal = goal or "Propose additional high-value test scenarios for this contract."
    return [
        {
            "role": "system",
            "content": (
                "You are the TestData Factory generator agent. Return only JSON that matches the requested schema. "
                "Propose scenario definitions that can be appended to contract.scenarios. Do not rewrite fields, "
                "generation settings, or validation metadata. Prefer existing deterministic strategies and explicit "
                "values from the TestData Factory contract format."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "goal": requested_goal,
                    "contract": contract,
                    "allowedScenarioKinds": ["positive", "negative", "boundary", "security"],
                    "outputContractPath": "proposal.scenarios",
                },
                indent=2,
                sort_keys=True,
            ),
        },
    ]


def _validator_messages(
    contract: dict[str, Any],
    proposal: dict[str, Any],
    local_result: ValidationResult,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are the TestData Factory validator agent. Return only JSON that matches the requested schema. "
                "Review whether the generator proposal is useful, deterministic, compatible with the existing "
                "contract fields, and safe to review into contract.scenarios."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "contract": contract,
                    "proposal": proposal,
                    "engineValidation": local_result.to_dict(),
                },
                indent=2,
                sort_keys=True,
            ),
        },
    ]


def _scenario_proposal_from_response(response: dict[str, Any]) -> dict[str, Any]:
    if isinstance(response.get("proposal"), dict):
        proposal = deepcopy(response["proposal"])
    elif isinstance(response.get("scenarios"), list):
        proposal = deepcopy(response)
    else:
        raise AIWorkflowError("Generator agent response must include proposal.scenarios as an array.")

    scenarios = proposal.get("scenarios")
    if not isinstance(scenarios, list):
        raise AIWorkflowError("Generator agent response must include proposal.scenarios as an array.")
    if not all(isinstance(scenario, dict) for scenario in scenarios):
        raise AIWorkflowError("Generator agent proposal.scenarios must contain JSON objects.")

    proposal.setdefault("summary", "AI-generated scenario plan.")
    proposal.setdefault("notes", [])
    return proposal


def _validation_result_from_response(response: dict[str, Any], *, agent_name: str) -> ValidationResult:
    status = response.get("status")
    if status not in VALIDATION_STATUSES:
        raise AIWorkflowError(f"{agent_name} response status must be one of: invalid, needs_review, valid.")

    score = response.get("score")
    if not isinstance(score, (int, float)):
        raise AIWorkflowError(f"{agent_name} response score must be a number.")
    score = min(1.0, max(0.0, float(score)))

    raw_findings = response.get("findings")
    if not isinstance(raw_findings, list):
        raise AIWorkflowError(f"{agent_name} response findings must be an array.")

    findings = tuple(_finding_from_response(finding, agent_name=agent_name) for finding in raw_findings)
    return ValidationResult(status=status, score=round(score, 2), findings=findings)


def _finding_from_response(finding: Any, *, agent_name: str) -> ValidationFinding:
    if not isinstance(finding, dict):
        raise AIWorkflowError(f"{agent_name} response findings must contain objects.")
    severity = finding.get("severity")
    if severity not in FINDING_SEVERITIES:
        raise AIWorkflowError(f"{agent_name} response finding severity must be one of: error, info, warning.")
    field = finding.get("field")
    if field is not None and not isinstance(field, str):
        raise AIWorkflowError(f"{agent_name} response finding field must be a string or null.")
    message = finding.get("message")
    recommendation = finding.get("recommendation")
    if not isinstance(message, str) or not message.strip():
        raise AIWorkflowError(f"{agent_name} response finding message is required.")
    if not isinstance(recommendation, str) or not recommendation.strip():
        raise AIWorkflowError(f"{agent_name} response finding recommendation is required.")
    return ValidationFinding(
        severity=severity,
        field=field,
        message=message,
        recommendation=recommendation,
    )


def _duplicate_scenario_findings(
    contract: dict[str, Any],
    scenarios: list[Any],
) -> list[ValidationFinding]:
    existing_ids = {
        str(scenario.get("id"))
        for scenario in contract.get("scenarios", [])
        if isinstance(scenario, dict) and isinstance(scenario.get("id"), str)
    }
    proposed_ids: set[str] = set()
    findings: list[ValidationFinding] = []
    for index, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict):
            continue
        scenario_id = scenario.get("id")
        if not isinstance(scenario_id, str):
            continue
        if scenario_id in existing_ids:
            findings.append(
                ValidationFinding(
                    severity="error",
                    field=f"proposal.scenarios[{index}].id",
                    message=f"Scenario id '{scenario_id}' already exists in the contract.",
                    recommendation="Use a new scenario id before adding the proposal to contract.scenarios.",
                )
            )
        if scenario_id in proposed_ids:
            findings.append(
                ValidationFinding(
                    severity="error",
                    field=f"proposal.scenarios[{index}].id",
                    message=f"Scenario id '{scenario_id}' is repeated in the proposal.",
                    recommendation="Keep scenario ids unique within the proposal.",
                )
            )
        proposed_ids.add(scenario_id)
    return findings


def _merge_validation_results(validator_result: ValidationResult, local_result: ValidationResult) -> ValidationResult:
    local_actionable = [finding for finding in local_result.findings if finding.severity != "info"]
    if not local_actionable:
        return validator_result

    findings = list(validator_result.findings)
    seen = {(finding.severity, finding.field, finding.message) for finding in findings}
    for finding in local_actionable:
        key = (finding.severity, finding.field, finding.message)
        if key not in seen:
            findings.append(finding)
            seen.add(key)

    merged = _result_from_findings(findings)
    status = merged.status
    if validator_result.status == "invalid":
        status = "invalid"
    elif validator_result.status == "needs_review" and status == "valid":
        status = "needs_review"
    return ValidationResult(
        status=status,
        score=min(validator_result.score, merged.score),
        findings=tuple(findings),
    )


def _result_from_findings(findings: list[ValidationFinding]) -> ValidationResult:
    error_count = sum(1 for finding in findings if finding.severity == "error")
    warning_count = sum(1 for finding in findings if finding.severity == "warning")
    if error_count:
        status = "invalid"
    elif warning_count:
        status = "needs_review"
    else:
        status = "valid"
    score = max(0.0, 1.0 - (error_count * 0.25) - (warning_count * 0.1))
    return ValidationResult(status=status, score=round(score, 2), findings=tuple(findings))


def _proposal_field(field: str | None, existing_count: int) -> str | None:
    if field is None or not field.startswith("scenarios["):
        return field
    close_index = field.find("]")
    if close_index == -1:
        return field
    try:
        scenario_index = int(field[len("scenarios[") : close_index])
    except ValueError:
        return field
    if scenario_index < existing_count:
        return field
    suffix = field[close_index + 1 :]
    return f"proposal.scenarios[{scenario_index - existing_count}]{suffix}"


def _validation_summary(result: ValidationResult) -> str:
    errors = [finding for finding in result.findings if finding.severity == "error"]
    if not errors:
        return result.status
    return "; ".join(f"{finding.field or '<root>'}: {finding.message}" for finding in errors)


SCENARIO_PROPOSAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["proposal"],
    "properties": {
        "proposal": {
            "type": "object",
            "additionalProperties": True,
            "required": ["summary", "scenarios"],
            "properties": {
                "summary": {"type": "string"},
                "notes": {"type": "array", "items": {"type": "string"}},
                "scenarios": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["id", "kind", "description", "fields"],
                        "properties": {
                            "id": {"type": "string"},
                            "kind": {"type": "string", "enum": ["positive", "negative", "boundary", "security"]},
                            "description": {"type": "string"},
                            "fields": {"type": "object", "additionalProperties": True},
                        },
                    },
                },
            },
        }
    },
}


VALIDATION_REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["status", "score", "findings"],
    "properties": {
        "status": {"type": "string", "enum": ["valid", "needs_review", "invalid"]},
        "score": {"type": "number", "minimum": 0, "maximum": 1},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["severity", "field", "message", "recommendation"],
                "properties": {
                    "severity": {"type": "string", "enum": ["info", "warning", "error"]},
                    "field": {"type": ["string", "null"]},
                    "message": {"type": "string"},
                    "recommendation": {"type": "string"},
                },
            },
        },
    },
}
