from __future__ import annotations

from pathlib import Path

import pytest

from testdata_factory_engine import GenerationError, generate_records, load_contract


ROOT = Path(__file__).resolve().parents[2]


def _contract():
    return load_contract(ROOT / "examples" / "contracts" / "register.tdf.json")


def test_generate_records_is_repeatable() -> None:
    contract = _contract()

    first = generate_records(contract, "valid_signup", count=2, seed="suite")
    second = generate_records(contract, "valid_signup", count=2, seed="suite")

    assert first == second


def test_generate_records_changes_with_seed() -> None:
    contract = _contract()

    first = generate_records(contract, "valid_signup", seed="suite-a")
    second = generate_records(contract, "valid_signup", seed="suite-b")

    assert first != second


def test_positive_record_covers_common_business_types() -> None:
    record = generate_records(_contract(), "valid_signup", seed="suite")[0]

    assert set(record) == {"firstName", "email", "phone", "password", "age", "plan", "birthDate", "newsletter"}
    assert record["email"].endswith("@example.test")
    assert record["phone"].startswith("+155501")
    assert 18 <= record["age"] <= 99
    assert record["plan"] in {"basic", "pro", "enterprise"}
    assert isinstance(record["newsletter"], bool)


def test_negative_scenario_overrides_only_target_field() -> None:
    record = generate_records(_contract(), "invalid_email_format", seed="suite")[0]

    assert record["email"] == "not-an-email"
    assert record["phone"].startswith("+155501")
    assert record["password"].startswith("Tdf!")


def test_unknown_scenario_fails_clearly() -> None:
    with pytest.raises(GenerationError, match="Unknown scenario"):
        generate_records(_contract(), "missing_scenario")
