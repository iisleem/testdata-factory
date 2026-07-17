from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .contracts import validate_contract_data
from .generation import GenerationError, generate_records
from .models import model_profiles_payload


class ContractPayload(BaseModel):
    contract: dict[str, Any]


class GeneratePayload(BaseModel):
    contract: dict[str, Any]
    scenario_id: str = Field(alias="scenarioId")
    count: int = 1
    seed: str | None = None


def create_app() -> FastAPI:
    app = FastAPI(
        title="TestData Factory API",
        version="0.1.0",
        description="Self-hosted API for contract validation and deterministic test data generation.",
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/model-profiles")
    def model_profiles() -> dict[str, Any]:
        return {"profiles": model_profiles_payload()}

    @app.post("/v1/contracts/validate")
    def validate_contract(payload: ContractPayload) -> dict[str, Any]:
        result = validate_contract_data(payload.contract).to_dict()
        contract_id = payload.contract.get("id")
        if isinstance(contract_id, str):
            result["id"] = contract_id
        return result

    @app.post("/v1/data/generate")
    def generate_data(payload: GeneratePayload) -> dict[str, Any]:
        try:
            records = generate_records(payload.contract, payload.scenario_id, count=payload.count, seed=payload.seed)
        except GenerationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"data": records}

    return app


app = create_app()
