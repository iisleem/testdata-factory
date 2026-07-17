from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from .contracts import Contract
from .seed import seeded_random

Field = dict[str, Any]
Strategy = Callable[[Field, str, str, int], Any]


class GenerationError(ValueError):
    """Raised when records cannot be generated from a contract."""


DEFAULT_STRATEGIES = {
    "first_name": "valid_first_name",
    "last_name": "valid_last_name",
    "full_name": "valid_full_name",
    "username": "valid_username",
    "email": "valid_email",
    "password": "valid_password",
    "phone_number": "valid_phone",
    "integer": "valid_integer",
    "quantity": "valid_integer",
    "decimal": "valid_decimal",
    "amount": "valid_decimal",
    "percentage": "valid_decimal",
    "enum": "valid_enum",
    "date": "valid_date",
    "date_of_birth": "valid_date",
    "boolean": "valid_boolean",
    "free_text": "valid_free_text",
}


def generate_records(
    contract: Contract | dict[str, Any],
    scenario_id: str,
    count: int = 1,
    seed: str | None = None,
) -> list[dict[str, Any]]:
    if count < 1:
        raise GenerationError("count must be greater than 0")

    data = contract.data if isinstance(contract, Contract) else contract
    scenario = _find_scenario(data, scenario_id)
    base_seed = seed or data["generation"]["defaultSeed"]

    return [_generate_record(data, scenario, scenario_id, base_seed, index) for index in range(count)]


def _generate_record(
    contract: dict[str, Any],
    scenario: dict[str, Any],
    scenario_id: str,
    seed: str,
    index: int,
) -> dict[str, Any]:
    record: dict[str, Any] = {}
    scenario_fields = scenario.get("fields", {})

    for field_name, field in contract["fields"].items():
        override = scenario_fields.get(field_name, {})
        if "value" in override:
            record[field_name] = override["value"]
            continue

        strategy_name = override.get("strategy") or _default_strategy(field)
        if strategy_name in {"missing", "missing_required"}:
            continue

        record[field_name] = _run_strategy(field, strategy_name, seed, scenario_id, index, field_name)

    return record


def _find_scenario(contract: dict[str, Any], scenario_id: str) -> dict[str, Any]:
    for scenario in contract["scenarios"]:
        if scenario["id"] == scenario_id:
            return scenario
    raise GenerationError(f"Unknown scenario: {scenario_id}")


def _default_strategy(field: Field) -> str:
    business_type = field["businessType"]
    try:
        return DEFAULT_STRATEGIES[business_type]
    except KeyError as exc:
        raise GenerationError(f"No default strategy for business type: {business_type}") from exc


def _run_strategy(
    field: Field,
    strategy_name: str,
    seed: str,
    scenario_id: str,
    index: int,
    field_name: str,
) -> Any:
    try:
        strategy = STRATEGIES[strategy_name]
    except KeyError as exc:
        raise GenerationError(f"Unknown strategy: {strategy_name}") from exc
    return strategy(field, seed, f"{scenario_id}:{field_name}", index)


def _rng(field: Field, seed: str, scope: str, index: int):
    return seeded_random(seed, scope, field["businessType"], index)


def _valid_first_name(field: Field, seed: str, scope: str, index: int) -> str:
    return _choice(field, seed, scope, index, ["Nora", "Maya", "Adam", "Omar", "Lina", "Sam"])


def _valid_last_name(field: Field, seed: str, scope: str, index: int) -> str:
    return _choice(field, seed, scope, index, ["Stone", "Rivera", "Saleh", "Carter", "Haddad", "Kim"])


def _valid_full_name(field: Field, seed: str, scope: str, index: int) -> str:
    first = _valid_first_name(field, seed, f"{scope}:first", index)
    last = _valid_last_name(field, seed, f"{scope}:last", index)
    return f"{first} {last}"


def _valid_username(field: Field, seed: str, scope: str, index: int) -> str:
    rng = _rng(field, seed, scope, index)
    return f"user_{rng.randint(1000, 9999)}"


def _valid_email(field: Field, seed: str, scope: str, index: int) -> str:
    rng = _rng(field, seed, scope, index)
    return f"user{index}.{rng.randint(1000, 9999)}@example.test"


def _invalid_email_format(field: Field, seed: str, scope: str, index: int) -> str:
    return "not-an-email"


def _valid_phone(field: Field, seed: str, scope: str, index: int) -> str:
    rng = _rng(field, seed, scope, index)
    country = field.get("constraints", {}).get("country", "US")
    if country == "US":
        return f"+155501{rng.randint(1000, 9999)}"
    return f"+100000{rng.randint(1000, 9999)}"


def _invalid_alpha(field: Field, seed: str, scope: str, index: int) -> str:
    return "abc"


def _valid_password(field: Field, seed: str, scope: str, index: int) -> str:
    rng = _rng(field, seed, scope, index)
    return f"Tdf!{rng.randint(100000, 999999)}Pass"


def _valid_integer(field: Field, seed: str, scope: str, index: int) -> int:
    constraints = field.get("constraints", {})
    minimum = int(constraints.get("minimum", 1))
    maximum = int(constraints.get("maximum", 999))
    return _rng(field, seed, scope, index).randint(minimum, maximum)


def _valid_decimal(field: Field, seed: str, scope: str, index: int) -> float:
    constraints = field.get("constraints", {})
    minimum = float(constraints.get("minimum", 1))
    maximum = float(constraints.get("maximum", 999))
    rng = _rng(field, seed, scope, index)
    return round(rng.uniform(minimum, maximum), 2)


def _valid_enum(field: Field, seed: str, scope: str, index: int) -> Any:
    values = field.get("constraints", {}).get("values")
    if not values:
        raise GenerationError("enum field requires constraints.values")
    return _choice(field, seed, scope, index, values)


def _valid_date(field: Field, seed: str, scope: str, index: int) -> str:
    rng = _rng(field, seed, scope, index)
    value = date(1990, 1, 1) + timedelta(days=rng.randint(0, 10_000))
    return value.isoformat()


def _valid_boolean(field: Field, seed: str, scope: str, index: int) -> bool:
    return bool(_rng(field, seed, scope, index).randint(0, 1))


def _valid_free_text(field: Field, seed: str, scope: str, index: int) -> str:
    return f"Generated test note {index + 1}"


def _choice(field: Field, seed: str, scope: str, index: int, values: list[Any]) -> Any:
    return values[_rng(field, seed, scope, index).randrange(len(values))]


STRATEGIES: dict[str, Strategy] = {
    "valid_first_name": _valid_first_name,
    "valid_last_name": _valid_last_name,
    "valid_full_name": _valid_full_name,
    "valid_username": _valid_username,
    "valid_email": _valid_email,
    "invalid_email_format": _invalid_email_format,
    "valid_phone": _valid_phone,
    "invalid_alpha": _invalid_alpha,
    "valid_password": _valid_password,
    "valid_integer": _valid_integer,
    "valid_decimal": _valid_decimal,
    "valid_enum": _valid_enum,
    "valid_date": _valid_date,
    "valid_boolean": _valid_boolean,
    "valid_free_text": _valid_free_text,
}
