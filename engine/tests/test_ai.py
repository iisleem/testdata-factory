from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from testdata_factory_engine.ai import AIWorkflowError, draft_scenarios_with_validation
from testdata_factory_engine.models import ModelProviderError


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = json.loads((ROOT / "examples" / "contracts" / "register.tdf.json").read_text(encoding="utf-8"))


class FakeProvider:
    provider_type = "fake"
    base_url = "memory://fake"
    model = "fake-model"

    def __init__(self, responses: list[dict[str, Any] | Exception]) -> None:
        self.responses = list(responses)
        self.requests: list[tuple[list[dict[str, str]], dict[str, Any]]] = []

    def chat_json(self, messages: list[dict[str, str]], response_schema: dict[str, Any]) -> dict[str, Any]:
        self.requests.append((messages, response_schema))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_dual_agent_scenario_assist_returns_proposal_and_validator_feedback() -> None:
    provider = FakeProvider(
        [
            {
                "proposal": {
                    "summary": "Add password and plan coverage.",
                    "scenarios": [
                        {
                            "id": "weak_password_security",
                            "kind": "security",
                            "description": "Password is common and should be rejected by the app.",
                            "fields": {"password": {"strategy": "weak_password"}},
                        }
                    ],
                    "notes": ["Review against app password policy."],
                }
            },
            {
                "status": "needs_review",
                "score": 0.9,
                "findings": [
                    {
                        "severity": "warning",
                        "field": "proposal.scenarios[0].fields.password",
                        "message": "Confirm the app rejects this weak password.",
                        "recommendation": "Run the scenario against the registration validation rules.",
                    }
                ],
            },
        ]
    )

    result = draft_scenarios_with_validation(CONTRACT, provider, model_profile="light", goal="Add security coverage")

    assert result.model_profile == "light"
    assert result.proposal["scenarios"][0]["id"] == "weak_password_security"
    assert result.validation.status == "needs_review"
    assert result.validation.findings[0].severity == "warning"
    assert len(provider.requests) == 2
    assert provider.requests[0][1]["required"] == ["proposal"]
    assert "generator agent" in provider.requests[0][0][0]["content"]
    assert "validator agent" in provider.requests[1][0][0]["content"]


def test_local_structural_feedback_is_preserved_when_validator_misses_it() -> None:
    provider = FakeProvider(
        [
            {
                "proposal": {
                    "summary": "Accidentally reuse an id.",
                    "scenarios": [
                        {
                            "id": "valid_signup",
                            "kind": "positive",
                            "description": "Duplicate of existing scenario.",
                            "fields": {"email": {"strategy": "valid_email"}},
                        }
                    ],
                }
            },
            {
                "status": "valid",
                "score": 1,
                "findings": [
                    {
                        "severity": "info",
                        "field": "proposal.scenarios",
                        "message": "Looks usable.",
                        "recommendation": "Review before committing.",
                    }
                ],
            },
        ]
    )

    result = draft_scenarios_with_validation(CONTRACT, provider)

    assert result.validation.status == "invalid"
    assert result.validation.score == 0.75
    assert any(
        finding.field == "proposal.scenarios[0].id"
        and finding.message == "Scenario id 'valid_signup' already exists in the contract."
        for finding in result.validation.findings
    )


def test_generator_response_without_scenarios_fails_clearly() -> None:
    provider = FakeProvider([{"proposal": {"summary": "No scenario array"}}])

    with pytest.raises(AIWorkflowError, match="proposal.scenarios"):
        draft_scenarios_with_validation(CONTRACT, provider)


def test_provider_model_failure_names_the_agent() -> None:
    provider = FakeProvider([ModelProviderError("ollama model response was not valid JSON.")])

    with pytest.raises(AIWorkflowError, match="Generator agent failed: ollama model response was not valid JSON"):
        draft_scenarios_with_validation(CONTRACT, provider)


def test_invalid_validator_response_fails_clearly() -> None:
    provider = FakeProvider(
        [
            {
                "proposal": {
                    "summary": "Add one scenario.",
                    "scenarios": [
                        {
                            "id": "plan_enterprise_boundary",
                            "kind": "boundary",
                            "description": "Use the last supported plan.",
                            "fields": {"plan": {"strategy": "valid_enum", "value": "enterprise"}},
                        }
                    ],
                }
            },
            {"status": "valid", "findings": []},
        ]
    )

    with pytest.raises(AIWorkflowError, match="Validator agent response score must be a number"):
        draft_scenarios_with_validation(CONTRACT, provider)
