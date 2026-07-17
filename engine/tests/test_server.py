from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from testdata_factory_engine.server import create_app


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = json.loads((ROOT / "examples" / "contracts" / "register.tdf.json").read_text(encoding="utf-8"))
INVALID_CONTRACT = json.loads(
    (ROOT / "examples" / "contracts" / "invalid-missing-fields.tdf.json").read_text(encoding="utf-8")
)
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
    body = response.json()
    assert body["status"] == "valid"
    assert body["score"] == 1
    assert body["id"] == "register"
    assert body["findings"][0]["severity"] == "info"


def test_validate_contract_endpoint_returns_structured_invalid_feedback() -> None:
    client = TestClient(create_app())

    response = client.post("/v1/contracts/validate", json={"contract": INVALID_CONTRACT})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "invalid"
    assert len(body["findings"]) >= 2
    assert {"fields", "scenarios"}.issubset({finding["field"] for finding in body["findings"]})
    assert all(finding["severity"] == "error" for finding in body["findings"])


def test_validate_contract_endpoint_reports_unknown_scenario_field() -> None:
    client = TestClient(create_app())
    contract = deepcopy(CONTRACT)
    contract["scenarios"][0]["fields"]["emali"] = {"strategy": "valid_email"}

    response = client.post("/v1/contracts/validate", json={"contract": contract})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "invalid"
    assert body["findings"][1] == {
        "severity": "error",
        "field": "scenarios[0].fields.emali",
        "message": "Scenario 'valid_signup' references unknown field 'emali'.",
        "recommendation": "Use a field defined in contract.fields or add a matching field definition.",
    }


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


def test_generate_data_endpoint_rejects_malformed_contract() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/data/generate",
        json={"contract": [], "scenarioId": "valid_signup"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "invalid"
    assert body["findings"][0]["field"] == "contract"
    assert body["findings"][0]["severity"] == "error"


def test_generate_data_endpoint_rejects_schema_invalid_contract() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/data/generate",
        json={"contract": INVALID_CONTRACT, "scenarioId": "valid_signup"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "invalid"
    assert len(body["findings"]) >= 2
    assert {"fields", "scenarios"}.issubset({finding["field"] for finding in body["findings"]})
    assert all(finding["severity"] == "error" for finding in body["findings"])


def test_generate_data_endpoint_rejects_unknown_scenario() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/data/generate",
        json={"contract": CONTRACT, "scenarioId": "missing_scenario"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "invalid"
    assert body["findings"] == [
        {
            "severity": "error",
            "field": "scenarioId",
            "message": "Unknown scenario: missing_scenario",
            "recommendation": "Use a scenario id defined in contract.scenarios.",
        }
    ]


def test_generate_data_endpoint_rejects_invalid_count() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/data/generate",
        json={"contract": CONTRACT, "scenarioId": "valid_signup", "count": 0},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "invalid"
    assert body["findings"][0]["field"] == "count"
    assert body["findings"][0]["recommendation"] == "Use a value greater than or equal to 1."


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
    assert "ValidationResult" in spec["components"]["schemas"]


def test_static_openapi_matches_live_schema_for_generation_contracts() -> None:
    client = TestClient(create_app())
    static = json.loads(OPENAPI_SPEC.read_text(encoding="utf-8"))
    live = client.get("/openapi.json").json()

    static_count = static["components"]["schemas"]["GeneratePayload"]["properties"]["count"]
    live_count = live["components"]["schemas"]["GeneratePayload"]["properties"]["count"]
    assert static_count["type"] == live_count["type"] == "integer"
    assert static_count["default"] == live_count["default"] == 1
    assert static_count["minimum"] == live_count["minimum"] == 1

    for path, status_code in [
        ("/v1/contracts/validate", "200"),
        ("/v1/data/generate", "200"),
        ("/v1/data/generate", "422"),
    ]:
        assert _response_schema(static, path, status_code) == _response_schema(live, path, status_code)


def _response_schema(spec: dict[str, object], path: str, status_code: str) -> dict[str, object]:
    paths = spec["paths"]
    assert isinstance(paths, dict)
    response = paths[path]["post"]["responses"][status_code]
    return response["content"]["application/json"]["schema"]
