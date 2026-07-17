from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from testdata_factory_engine.server import create_app


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = json.loads((ROOT / "examples" / "contracts" / "register.tdf.json").read_text(encoding="utf-8"))
OPENAPI_SPEC = ROOT / "specs" / "openapi" / "testdata-factory.openapi.json"


def test_health_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_validate_contract_endpoint() -> None:
    client = TestClient(create_app())

    response = client.post("/v1/contracts/validate", json={"contract": CONTRACT})

    assert response.status_code == 200
    assert response.json() == {"status": "valid", "id": "register"}


def test_generate_data_endpoint() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/data/generate",
        json={"contract": CONTRACT, "scenarioId": "invalid_email_format", "count": 1, "seed": "api"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["email"] == "not-an-email"


def test_model_profiles_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/v1/model-profiles")

    assert response.status_code == 200
    assert set(response.json()["profiles"]) == {"light", "balanced", "strong"}


def test_static_openapi_spec_is_valid_json() -> None:
    spec = json.loads(OPENAPI_SPEC.read_text(encoding="utf-8"))

    assert spec["openapi"].startswith("3.")
    assert "/health" in spec["paths"]
    assert "/v1/data/generate" in spec["paths"]
