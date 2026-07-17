from __future__ import annotations

import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from testdata_factory_engine import TestDataFactory
from testdata_factory_engine.server import create_app


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "engine" / "tests" / "fixtures"
REGISTER_CONTRACT = ROOT / "examples" / "contracts" / "register.tdf.json"


@pytest.mark.release_smoke
def test_release_cli_import_scan_validate_generate_workflow(tmp_path: Path) -> None:
    json_schema_contract = tmp_path / "customer-signup.tdf.json"
    openapi_contract = tmp_path / "create-customer.tdf.json"
    scanned_form_contract = tmp_path / "sample-form.tdf.json"

    _run_tdf(
        [
            "import",
            "json-schema",
            FIXTURES / "customer.schema.json",
            "--id",
            "release-customer-signup",
            "--out",
            json_schema_contract,
        ]
    )
    _assert_valid_contract(json_schema_contract)
    json_schema_records = _generate_records(json_schema_contract, "valid_payload", count=2)
    assert [record["email"].endswith("@example.test") for record in json_schema_records] == [True, True]
    assert {record["plan"] for record in json_schema_records}.issubset({"basic", "pro", "enterprise"})

    _run_tdf(
        [
            "import",
            "openapi",
            FIXTURES / "customer.openapi.json",
            "--operation",
            "createCustomer",
            "--id",
            "release-create-customer",
            "--out",
            openapi_contract,
        ]
    )
    _assert_valid_contract(openapi_contract)
    openapi_records = _generate_records(openapi_contract, "valid_payload", count=2)
    assert {record["role"] for record in openapi_records}.issubset({"admin", "member"})
    assert all(isinstance(record["marketingOptIn"], bool) for record in openapi_records)

    _run_tdf(
        [
            "scan",
            "--url",
            FIXTURES / "sample_form.html",
            "--id",
            "release-sample-form",
            "--out",
            scanned_form_contract,
            "--country",
            "US",
        ]
    )
    _assert_valid_contract(scanned_form_contract)
    form_records = _generate_records(scanned_form_contract, "valid_form", count=1)
    assert set(form_records[0]) == {"firstName", "email", "quantity", "website", "plan", "notes"}
    assert form_records[0]["website"].startswith("https://")
    assert form_records[0]["plan"] in {"basic", "pro"}


@pytest.mark.release_smoke
def test_release_api_validate_generate_and_structured_422_feedback() -> None:
    client = TestClient(create_app())
    contract = json.loads(REGISTER_CONTRACT.read_text(encoding="utf-8"))

    assert client.get("/health").json() == {"status": "ok"}
    assert set(client.get("/v1/model-profiles").json()["profiles"]) == {"light", "balanced", "strong"}

    validation = client.post("/v1/contracts/validate", json={"contract": contract})
    assert validation.status_code == 200
    assert validation.json()["status"] == "valid"

    generate_payload = {
        "contract": contract,
        "scenarioId": "valid_signup",
        "count": 2,
        "seed": "release-api",
    }
    generated = client.post("/v1/data/generate", json=generate_payload)
    repeated = client.post("/v1/data/generate", json=generate_payload)
    assert generated.status_code == 200
    assert repeated.status_code == 200
    assert generated.json() == repeated.json()
    assert len(generated.json()["data"]) == 2

    invalid_contract = deepcopy(contract)
    invalid_contract.pop("fields")
    invalid = client.post(
        "/v1/data/generate",
        json={"contract": invalid_contract, "scenarioId": "valid_signup", "count": 1},
    )

    assert invalid.status_code == 422
    body = invalid.json()
    assert body["status"] == "invalid"
    assert body["findings"][0]["field"] == "fields"
    assert body["findings"][0]["severity"] == "error"
    assert body["findings"][0]["recommendation"] == "Add the required property to the contract."


@pytest.mark.release_smoke
def test_release_python_sdk_generation_workflow() -> None:
    client = TestDataFactory.local().seed("release-python-sdk")

    first = client.contract(REGISTER_CONTRACT).scenario("valid_signup").count(2)
    second = client.contract(REGISTER_CONTRACT).scenario("valid_signup").count(2)

    assert first == second
    assert len(first) == 2
    assert all(record["email"].endswith("@example.test") for record in first)


def _assert_valid_contract(contract_path: Path) -> None:
    validation = json.loads(_run_tdf(["validate", "--json", contract_path]).stdout)
    assert validation["status"] == "valid"
    assert validation["score"] == 1.0


def _generate_records(contract_path: Path, scenario_id: str, *, count: int) -> list[dict[str, Any]]:
    result = _run_tdf(
        [
            "generate",
            "--contract",
            contract_path,
            "--scenario",
            scenario_id,
            "--count",
            str(count),
            "--seed",
            "release-cli",
        ]
    )
    repeated = _run_tdf(
        [
            "generate",
            "--contract",
            contract_path,
            "--scenario",
            scenario_id,
            "--count",
            str(count),
            "--seed",
            "release-cli",
        ]
    )
    assert result.stdout == repeated.stdout
    records = json.loads(result.stdout)
    assert isinstance(records, list)
    assert len(records) == count
    return records


def _run_tdf(args: list[object]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = _pythonpath()
    result = subprocess.run(
        [sys.executable, "-m", "testdata_factory_engine.cli", *(str(arg) for arg in args)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def _pythonpath() -> str:
    current = os.environ.get("PYTHONPATH")
    paths = [str(ROOT / "engine" / "src")]
    if current:
        paths.append(current)
    return os.pathsep.join(paths)
