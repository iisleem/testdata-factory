from __future__ import annotations

from pathlib import Path

import pytest

from testdata_factory_engine import ContractValidationError, load_contract


ROOT = Path(__file__).resolve().parents[2]


def test_loads_valid_contract() -> None:
    contract = load_contract(ROOT / "examples" / "contracts" / "register.tdf.json")

    assert contract.id == "register"
    assert contract.data["fields"]["email"]["businessType"] == "email"


def test_rejects_invalid_contract() -> None:
    with pytest.raises(ContractValidationError, match="fields"):
        load_contract(ROOT / "examples" / "contracts" / "invalid-missing-fields.tdf.json")
