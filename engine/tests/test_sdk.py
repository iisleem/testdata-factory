from __future__ import annotations

from pathlib import Path

from testdata_factory_engine import TestDataFactory


ROOT = Path(__file__).resolve().parents[2]


def test_python_sdk_generates_one_record() -> None:
    user = (
        TestDataFactory.local()
        .seed("python-sdk")
        .contract(ROOT / "examples" / "contracts" / "register.tdf.json")
        .scenario("valid_signup")
        .one()
    )

    assert user["email"].endswith("@example.test")


def test_python_sdk_generation_is_repeatable() -> None:
    first = (
        TestDataFactory.local()
        .seed("python-sdk")
        .contract(ROOT / "examples" / "contracts" / "register.tdf.json")
        .scenario("valid_signup")
        .count(2)
    )
    second = (
        TestDataFactory.local()
        .seed("python-sdk")
        .contract(ROOT / "examples" / "contracts" / "register.tdf.json")
        .scenario("valid_signup")
        .count(2)
    )

    assert first == second


def test_python_sdk_generates_requested_count() -> None:
    users = (
        TestDataFactory.local()
        .seed("python-sdk")
        .contract(ROOT / "examples" / "contracts" / "register.tdf.json")
        .scenario("valid_signup")
        .count(2)
    )

    assert len(users) == 2
    assert users[0]["phone"].startswith("+155501")
    assert users[0]["plan"] in {"basic", "pro", "enterprise"}


def test_python_sdk_applies_negative_scenario_strategy() -> None:
    user = (
        TestDataFactory.local()
        .seed("python-sdk")
        .contract(ROOT / "examples" / "contracts" / "register.tdf.json")
        .scenario("invalid_email_format")
        .one()
    )

    assert user["email"] == "not-an-email"
    assert user["password"].startswith("Tdf!")
