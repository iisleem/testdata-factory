from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .ai import AIWorkflowError, draft_scenarios_with_validation
from .contracts import (
    FindingSeverity,
    ValidationFinding as ContractValidationFinding,
    ValidationResult as ContractValidationResult,
    ValidationStatus,
    validate_contract_data,
)
from .generation import GenerationError, generate_records
from .models import LocalModelProvider, ProviderConfig, create_provider, get_model_profile, model_profiles_payload, parse_provider_config


class ContractPayload(BaseModel):
    contract: dict[str, Any]


class GeneratePayload(BaseModel):
    contract: dict[str, Any]
    scenario_id: str = Field(alias="scenarioId")
    count: int = Field(default=1, ge=1)
    seed: str | None = None


class AIScenarioAssistPayload(BaseModel):
    contract: dict[str, Any]
    provider: dict[str, Any]
    model_profile: str = Field(default="balanced", alias="modelProfile")
    goal: str | None = None


class ValidationFinding(BaseModel):
    severity: FindingSeverity
    field: str | None
    message: str
    recommendation: str


class ValidationResult(BaseModel):
    id: str | None = None
    status: ValidationStatus
    score: float = Field(ge=0, le=1)
    findings: list[ValidationFinding]


class GenerateResponse(BaseModel):
    data: list[dict[str, Any]]


class AIProviderMetadata(BaseModel):
    provider_type: str = Field(alias="type")
    model: str


class AIScenarioAssistResponse(BaseModel):
    mode: str
    model_profile: str = Field(alias="modelProfile")
    provider: AIProviderMetadata
    proposal: dict[str, Any]
    validation: ValidationResult


def create_app(provider_factory: Callable[[ProviderConfig], LocalModelProvider] = create_provider) -> FastAPI:
    app = FastAPI(
        title="TestData Factory API",
        version="1.0.0",
        description="Self-hosted API for contract validation and deterministic test data generation.",
    )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: RequestValidationError):
        if request.url.path in {"/v1/data/generate", "/v1/ai/scenarios"}:
            return _validation_json_response(_request_validation_result(exc.errors()))
        return await request_validation_exception_handler(request, exc)

    @app.get("/health", summary="Health check")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/model-profiles", summary="List local model profiles")
    def model_profiles() -> dict[str, Any]:
        return {"profiles": model_profiles_payload()}

    @app.post(
        "/v1/contracts/validate",
        summary="Validate a contract",
        response_model=ValidationResult,
        response_model_exclude_none=True,
        response_description="Structured contract validation feedback",
    )
    def validate_contract(payload: ContractPayload) -> dict[str, Any]:
        return _validation_payload(validate_contract_data(payload.contract), payload.contract)

    @app.post(
        "/v1/data/generate",
        summary="Generate deterministic test data",
        response_model=GenerateResponse,
        response_description="Generated test data",
        responses={422: {"model": ValidationResult, "description": "Structured validation feedback"}},
    )
    def generate_data(payload: GeneratePayload):
        validation_result = validate_contract_data(payload.contract)
        if not validation_result.is_valid:
            return _validation_json_response(validation_result, payload.contract)
        try:
            records = generate_records(payload.contract, payload.scenario_id, count=payload.count, seed=payload.seed)
        except GenerationError as exc:
            return _validation_json_response(_generation_error_result(str(exc)), payload.contract)
        return {"data": records}

    @app.post(
        "/v1/ai/scenarios",
        summary="Draft scenario additions with local AI validation",
        response_model=AIScenarioAssistResponse,
        response_description="AI scenario proposal and structured validation feedback",
        responses={
            422: {"model": ValidationResult, "description": "Structured validation feedback"},
            502: {"model": ValidationResult, "description": "Local model provider failure"},
        },
    )
    def ai_scenarios(payload: AIScenarioAssistPayload):
        validation_result = validate_contract_data(payload.contract)
        if not validation_result.is_valid:
            return _validation_json_response(validation_result, payload.contract)

        try:
            get_model_profile(payload.model_profile)
            provider_config = parse_provider_config(payload.provider, profile=payload.model_profile)
            provider = provider_factory(provider_config)
        except ValueError as exc:
            return _validation_json_response(
                _ai_error_result(
                    "provider",
                    str(exc),
                    "Provide a local provider config with type, baseUrl, model, and an optional local profile override.",
                ),
                payload.contract,
            )

        try:
            result = draft_scenarios_with_validation(
                payload.contract,
                provider,
                model_profile=payload.model_profile,
                goal=payload.goal,
            )
        except AIWorkflowError as exc:
            return JSONResponse(
                status_code=502,
                content=_validation_payload(
                    _ai_error_result(
                        "provider",
                        str(exc),
                        "Check that the local model is running and returning the required JSON shape.",
                    ),
                    payload.contract,
                ),
            )
        return result.to_dict()

    return app


def _validation_json_response(
    result: ContractValidationResult,
    contract: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(status_code=422, content=_validation_payload(result, contract))


def _validation_payload(result: ContractValidationResult, contract: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = result.to_dict()
    if contract is not None:
        contract_id = contract.get("id")
        if isinstance(contract_id, str):
            payload["id"] = contract_id
    return payload


def _request_validation_result(errors: list[dict[str, Any]]) -> ContractValidationResult:
    findings = [
        ContractValidationFinding(
            severity="error",
            field=_request_error_field(error),
            message=str(error.get("msg", "Request payload is invalid.")),
            recommendation=_request_error_recommendation(error),
        )
        for error in errors
    ]
    return _invalid_result(findings)


def _generation_error_result(message: str) -> ContractValidationResult:
    field = "scenarioId" if message.startswith("Unknown scenario:") else None
    recommendation = (
        "Use a scenario id defined in contract.scenarios."
        if field == "scenarioId"
        else "Update the contract or generation request so data can be generated."
    )
    return _invalid_result(
        [
            ContractValidationFinding(
                severity="error",
                field=field,
                message=message,
                recommendation=recommendation,
            )
        ]
    )


def _ai_error_result(field: str | None, message: str, recommendation: str) -> ContractValidationResult:
    return _invalid_result(
        [
            ContractValidationFinding(
                severity="error",
                field=field,
                message=message,
                recommendation=recommendation,
            )
        ]
    )


def _invalid_result(findings: list[ContractValidationFinding]) -> ContractValidationResult:
    score = max(0.0, 1.0 - (len(findings) * 0.25))
    return ContractValidationResult(status="invalid", score=round(score, 2), findings=tuple(findings))


def _request_error_field(error: dict[str, Any]) -> str | None:
    location = error.get("loc", ())
    if not isinstance(location, (list, tuple)):
        return None
    parts = [str(part) for part in location if part != "body"]
    return ".".join(parts) or None


def _request_error_recommendation(error: dict[str, Any]) -> str:
    field = _request_error_field(error)
    error_type = str(error.get("type", ""))
    if error_type == "missing":
        return "Provide the required request property."
    if error_type == "greater_than_equal":
        minimum = error.get("ctx", {}).get("ge", 1)
        return f"Use a value greater than or equal to {minimum}."
    if field == "contract":
        return "Provide contract as a JSON object that follows the TestData Factory contract schema."
    return "Update the request payload so it matches the API schema."


app = create_app()
