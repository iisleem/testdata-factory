from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "engine" / "src"))

from testdata_factory_engine import TestDataFactory

CONTRACT = ROOT / "examples" / "contracts" / "register.tdf.json"


def test_valid_signup_data_for_registration_flow() -> None:
    users = (
        TestDataFactory.local()
        .seed("pytest-registration-flow")
        .contract(CONTRACT)
        .scenario("valid_signup")
        .count(2)
    )

    assert len(users) == 2
    assert users[0]["email"].endswith("@example.test")
    assert users[0]["phone"].startswith("+155501")
    assert users[0]["plan"] in {"basic", "pro", "enterprise"}


def test_negative_signup_data_for_email_validation() -> None:
    user = (
        TestDataFactory.local()
        .seed("pytest-registration-flow")
        .contract(CONTRACT)
        .scenario("invalid_email_format")
        .one()
    )

    assert user["email"] == "not-an-email"
    assert user["password"].startswith("Tdf!")
