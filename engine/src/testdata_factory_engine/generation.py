from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date, datetime, time, timedelta
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
    "country_code": "valid_country_code",
    "address_line": "valid_address_line",
    "city": "valid_city",
    "state": "valid_state",
    "postal_code": "valid_postal_code",
    "country": "valid_country",
    "date": "valid_date",
    "date_of_birth": "valid_date",
    "time": "valid_time",
    "datetime": "valid_datetime",
    "amount": "valid_decimal",
    "currency": "valid_currency",
    "percentage": "valid_decimal",
    "integer": "valid_integer",
    "quantity": "valid_integer",
    "decimal": "valid_decimal",
    "boolean": "valid_boolean",
    "enum": "valid_enum",
    "url": "valid_url",
    "domain": "valid_domain",
    "uuid": "valid_uuid",
    "national_id": "valid_national_id",
    "passport_number": "valid_passport_number",
    "tax_id": "valid_tax_id",
    "account_number": "valid_account_number",
    "iban": "valid_iban",
    "credit_card_number": "valid_credit_card_number",
    "cvv": "valid_cvv",
    "expiry_date": "valid_expiry_date",
    "otp": "valid_otp",
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


def _valid_country_code(field: Field, seed: str, scope: str, index: int) -> str:
    return _choice(field, seed, scope, index, ["US", "CA", "GB", "AU", "DE", "FR", "JO"])


def _valid_address_line(field: Field, seed: str, scope: str, index: int) -> str:
    rng = _rng(field, seed, scope, index)
    streets = ["Market Street", "Cedar Avenue", "River Road", "Summit Lane", "Atlas Way"]
    return f"{rng.randint(100, 999)} {streets[rng.randrange(len(streets))]}"


def _valid_city(field: Field, seed: str, scope: str, index: int) -> str:
    return _choice(field, seed, scope, index, ["Springfield", "Riverton", "Fairview", "Georgetown", "Franklin"])


def _valid_state(field: Field, seed: str, scope: str, index: int) -> str:
    return _choice(field, seed, scope, index, ["CA", "NY", "TX", "WA", "IL", "FL"])


def _valid_postal_code(field: Field, seed: str, scope: str, index: int) -> str:
    return f"{_rng(field, seed, scope, index).randint(10000, 99999)}"


def _valid_country(field: Field, seed: str, scope: str, index: int) -> str:
    return _choice(
        field,
        seed,
        scope,
        index,
        ["United States", "Canada", "United Kingdom", "Australia", "Germany", "France", "Jordan"],
    )


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


def _valid_time(field: Field, seed: str, scope: str, index: int) -> str:
    rng = _rng(field, seed, scope, index)
    value = time(hour=rng.randint(0, 23), minute=rng.randint(0, 59), second=0)
    return value.isoformat()


def _valid_datetime(field: Field, seed: str, scope: str, index: int) -> str:
    rng = _rng(field, seed, scope, index)
    value = datetime(2024, 1, 1, 9, 0, 0) + timedelta(
        days=rng.randint(0, 365),
        minutes=rng.randint(0, 8 * 60),
    )
    return f"{value.isoformat()}Z"


def _valid_boolean(field: Field, seed: str, scope: str, index: int) -> bool:
    return bool(_rng(field, seed, scope, index).randint(0, 1))


def _valid_currency(field: Field, seed: str, scope: str, index: int) -> str:
    return _choice(field, seed, scope, index, ["USD", "EUR", "GBP", "CAD", "AUD", "JPY", "JOD"])


def _valid_url(field: Field, seed: str, scope: str, index: int) -> str:
    rng = _rng(field, seed, scope, index)
    return f"https://app-{rng.randint(100, 999)}.example.test/resource-{index + 1}"


def _valid_domain(field: Field, seed: str, scope: str, index: int) -> str:
    rng = _rng(field, seed, scope, index)
    return f"service-{rng.randint(100, 999)}.example.test"


def _valid_uuid(field: Field, seed: str, scope: str, index: int) -> str:
    value = f"{seed}:{scope}:{field['businessType']}:{index}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, value))


def _valid_national_id(field: Field, seed: str, scope: str, index: int) -> str:
    return f"NID-{_rng(field, seed, scope, index).randint(100000000, 999999999)}"


def _valid_passport_number(field: Field, seed: str, scope: str, index: int) -> str:
    rng = _rng(field, seed, scope, index)
    prefix = ["P", "T", "X"][rng.randrange(3)]
    return f"{prefix}{rng.randint(10000000, 99999999)}"


def _valid_tax_id(field: Field, seed: str, scope: str, index: int) -> str:
    return f"TAX-{_rng(field, seed, scope, index).randint(10000000, 99999999)}"


def _valid_account_number(field: Field, seed: str, scope: str, index: int) -> str:
    return f"000{_rng(field, seed, scope, index).randint(100000000, 999999999)}"


def _valid_iban(field: Field, seed: str, scope: str, index: int) -> str:
    rng = _rng(field, seed, scope, index)
    bban = f"TEST123456{rng.randint(0, 99999999):08d}"
    return f"GB{_iban_check_digits('GB', bban)}{bban}"


def _valid_credit_card_number(field: Field, seed: str, scope: str, index: int) -> str:
    rng = _rng(field, seed, scope, index)
    body = f"411111{rng.randint(0, 999999999):09d}"
    return f"{body}{_luhn_check_digit(body)}"


def _valid_cvv(field: Field, seed: str, scope: str, index: int) -> str:
    return f"{_rng(field, seed, scope, index).randint(0, 999):03d}"


def _valid_expiry_date(field: Field, seed: str, scope: str, index: int) -> str:
    rng = _rng(field, seed, scope, index)
    month = rng.randint(1, 12)
    year = 30 + rng.randint(0, 9)
    return f"{month:02d}/{year:02d}"


def _valid_otp(field: Field, seed: str, scope: str, index: int) -> str:
    return f"{_rng(field, seed, scope, index).randint(0, 999999):06d}"


def _valid_free_text(field: Field, seed: str, scope: str, index: int) -> str:
    return f"Generated test note {index + 1}"


def _choice(field: Field, seed: str, scope: str, index: int, values: list[Any]) -> Any:
    return values[_rng(field, seed, scope, index).randrange(len(values))]


def _iban_check_digits(country_code: str, bban: str) -> str:
    remainder = _iban_mod97(f"{bban}{country_code}00")
    return f"{98 - remainder:02d}"


def _iban_mod97(value: str) -> int:
    remainder = 0
    for char in value.upper():
        if char.isdigit():
            digits = char
        elif char.isalpha():
            digits = str(ord(char) - 55)
        else:
            continue
        for digit in digits:
            remainder = (remainder * 10 + int(digit)) % 97
    return remainder


def _luhn_check_digit(number: str) -> str:
    total = 0
    for index, char in enumerate(reversed(number)):
        digit = int(char)
        if index % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return str((10 - total % 10) % 10)


STRATEGIES: dict[str, Strategy] = {
    "valid_first_name": _valid_first_name,
    "valid_last_name": _valid_last_name,
    "valid_full_name": _valid_full_name,
    "valid_username": _valid_username,
    "valid_email": _valid_email,
    "invalid_email_format": _invalid_email_format,
    "valid_phone": _valid_phone,
    "valid_country_code": _valid_country_code,
    "valid_address_line": _valid_address_line,
    "valid_city": _valid_city,
    "valid_state": _valid_state,
    "valid_postal_code": _valid_postal_code,
    "valid_country": _valid_country,
    "invalid_alpha": _invalid_alpha,
    "valid_password": _valid_password,
    "valid_integer": _valid_integer,
    "valid_decimal": _valid_decimal,
    "valid_enum": _valid_enum,
    "valid_date": _valid_date,
    "valid_time": _valid_time,
    "valid_datetime": _valid_datetime,
    "valid_boolean": _valid_boolean,
    "valid_currency": _valid_currency,
    "valid_url": _valid_url,
    "valid_domain": _valid_domain,
    "valid_uuid": _valid_uuid,
    "valid_national_id": _valid_national_id,
    "valid_passport_number": _valid_passport_number,
    "valid_tax_id": _valid_tax_id,
    "valid_account_number": _valid_account_number,
    "valid_iban": _valid_iban,
    "valid_credit_card_number": _valid_credit_card_number,
    "valid_cvv": _valid_cvv,
    "valid_expiry_date": _valid_expiry_date,
    "valid_otp": _valid_otp,
    "valid_free_text": _valid_free_text,
}
