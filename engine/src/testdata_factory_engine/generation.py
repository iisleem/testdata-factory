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

RELATIONAL_STRATEGIES = {
    "match_field",
    "mismatch_field",
    "range_end_after_start",
    "date_after_related_field",
    "date_before_related_field",
    "numeric_max_at_or_above_min",
    "numeric_max_below_min",
}
INDEPENDENT_VALUE_STRATEGIES = {
    "xss_payload",
    "sql_injection_payload",
    "null_value",
    "empty_string",
    "whitespace_only",
    "over_max_length",
    "below_min_length",
    "duplicate_value",
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

        if strategy_name in RELATIONAL_STRATEGIES:
            strategy_name = _default_strategy(field)

        record[field_name] = _run_strategy(field, strategy_name, seed, scenario_id, index, field_name)

    _apply_dependencies(record, contract, scenario)
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
    return _bounded_text(field, _choice(field, seed, scope, index, ["Nora", "Maya", "Adam", "Omar", "Lina", "Sam"]))


def _valid_last_name(field: Field, seed: str, scope: str, index: int) -> str:
    return _bounded_text(field, _choice(field, seed, scope, index, ["Stone", "Rivera", "Saleh", "Carter", "Haddad", "Kim"]))


def _valid_full_name(field: Field, seed: str, scope: str, index: int) -> str:
    first = _valid_first_name(field, seed, f"{scope}:first", index)
    last = _valid_last_name(field, seed, f"{scope}:last", index)
    return _bounded_text(field, f"{first} {last}")


def _valid_username(field: Field, seed: str, scope: str, index: int) -> str:
    rng = _rng(field, seed, scope, index)
    return _bounded_text(field, f"user_{rng.randint(1000, 9999)}")


def _valid_email(field: Field, seed: str, scope: str, index: int) -> str:
    rng = _rng(field, seed, scope, index)
    return _bounded_email(field, f"user{index}.{rng.randint(1000, 9999)}@example.test")


def _invalid_email_format(field: Field, seed: str, scope: str, index: int) -> str:
    return "not-an-email"


def _valid_phone(field: Field, seed: str, scope: str, index: int) -> str:
    rng = _rng(field, seed, scope, index)
    country = field.get("constraints", {}).get("country", "US")
    if country == "US":
        return _bounded_text(field, f"+155501{rng.randint(1000, 9999)}", filler="0")
    return _bounded_text(field, f"+100000{rng.randint(1000, 9999)}", filler="0")


def _invalid_phone_format(field: Field, seed: str, scope: str, index: int) -> str:
    return "not-a-phone"


def _valid_country_code(field: Field, seed: str, scope: str, index: int) -> str:
    return _choice(field, seed, scope, index, ["US", "CA", "GB", "AU", "DE", "FR", "JO"])


def _valid_address_line(field: Field, seed: str, scope: str, index: int) -> str:
    rng = _rng(field, seed, scope, index)
    streets = ["Market Street", "Cedar Avenue", "River Road", "Summit Lane", "Atlas Way"]
    return _bounded_text(field, f"{rng.randint(100, 999)} {streets[rng.randrange(len(streets))]}")


def _valid_city(field: Field, seed: str, scope: str, index: int) -> str:
    return _bounded_text(field, _choice(field, seed, scope, index, ["Springfield", "Riverton", "Fairview", "Georgetown", "Franklin"]))


def _valid_state(field: Field, seed: str, scope: str, index: int) -> str:
    return _bounded_text(field, _choice(field, seed, scope, index, ["CA", "NY", "TX", "WA", "IL", "FL"]))


def _valid_postal_code(field: Field, seed: str, scope: str, index: int) -> str:
    return _bounded_text(field, f"{_rng(field, seed, scope, index).randint(10000, 99999)}", filler="0")


def _valid_country(field: Field, seed: str, scope: str, index: int) -> str:
    return _bounded_text(
        field,
        _choice(
            field,
            seed,
            scope,
            index,
            ["United States", "Canada", "United Kingdom", "Australia", "Germany", "France", "Jordan"],
        ),
    )


def _invalid_alpha(field: Field, seed: str, scope: str, index: int) -> str:
    return "abc"


def _valid_password(field: Field, seed: str, scope: str, index: int) -> str:
    rng = _rng(field, seed, scope, index)
    return _bounded_text(field, f"Tdf!{rng.randint(100000, 999999)}Pass", filler="A")


def _weak_password(field: Field, seed: str, scope: str, index: int) -> str:
    return "password"


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


def _boolean_false(field: Field, seed: str, scope: str, index: int) -> bool:
    return False


def _boolean_true(field: Field, seed: str, scope: str, index: int) -> bool:
    return True


def _valid_currency(field: Field, seed: str, scope: str, index: int) -> str:
    return _bounded_text(field, _choice(field, seed, scope, index, ["USD", "EUR", "GBP", "CAD", "AUD", "JPY", "JOD"]))


def _valid_url(field: Field, seed: str, scope: str, index: int) -> str:
    rng = _rng(field, seed, scope, index)
    return _bounded_url(field, f"https://app-{rng.randint(100, 999)}.example.test/resource-{index + 1}")


def _valid_domain(field: Field, seed: str, scope: str, index: int) -> str:
    rng = _rng(field, seed, scope, index)
    return _bounded_domain(field, f"service-{rng.randint(100, 999)}.example.test")


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
    return _bounded_text(field, f"Generated test note {index + 1}")


def _xss_payload(field: Field, seed: str, scope: str, index: int) -> str:
    return "<script>alert('tdf')</script>"


def _sql_injection_payload(field: Field, seed: str, scope: str, index: int) -> str:
    return "admin' OR '1'='1"


def _null_value(field: Field, seed: str, scope: str, index: int) -> None:
    return None


def _empty_string(field: Field, seed: str, scope: str, index: int) -> str:
    return ""


def _whitespace_only(field: Field, seed: str, scope: str, index: int) -> str:
    return "   "


def _over_max_length(field: Field, seed: str, scope: str, index: int) -> str:
    maximum = field.get("constraints", {}).get("maxLength")
    length = maximum + 1 if isinstance(maximum, int) and maximum >= 0 else 256
    return "X" * length


def _below_min_length(field: Field, seed: str, scope: str, index: int) -> str:
    minimum = field.get("constraints", {}).get("minLength")
    length = minimum - 1 if isinstance(minimum, int) and minimum > 0 else 0
    return "A" * length


def _duplicate_value(field: Field, seed: str, scope: str, index: int) -> Any:
    business_type = field.get("businessType")
    if business_type == "email":
        return _bounded_email(field, "duplicate@example.test")
    if business_type == "username":
        return _bounded_text(field, "duplicate_user")
    if business_type == "uuid":
        return "00000000-0000-4000-8000-000000000000"
    if business_type in {"integer", "quantity"}:
        return _integer_minimum(field)
    if business_type in {"decimal", "amount", "percentage"}:
        return float(_numeric_minimum(field))
    if business_type in {"date", "date_of_birth"}:
        return "2026-01-01"
    return _bounded_text(field, "duplicate")


def _choice(field: Field, seed: str, scope: str, index: int, values: list[Any]) -> Any:
    return values[_rng(field, seed, scope, index).randrange(len(values))]


def _apply_dependencies(record: dict[str, Any], contract: dict[str, Any], scenario: dict[str, Any]) -> None:
    scenario_fields = scenario.get("fields", {})
    if not isinstance(scenario_fields, dict):
        scenario_fields = {}

    for field_name, field in contract["fields"].items():
        if field_name not in record:
            continue

        override = scenario_fields.get(field_name, {})
        if isinstance(override, dict) and "value" in override:
            continue

        dependencies = field.get("dependencies", {})
        if not isinstance(dependencies, dict):
            continue

        strategy_name = str(override.get("strategy", "")) if isinstance(override, dict) else ""
        if strategy_name in INDEPENDENT_VALUE_STRATEGIES:
            continue

        matches_field = dependencies.get("matchesField")
        if isinstance(matches_field, str) and matches_field in record:
            if strategy_name == "mismatch_field":
                record[field_name] = _different_value(record[matches_field], field)
            else:
                record[field_name] = record[matches_field]
            continue

        range_start = dependencies.get("rangeEndFor")
        if isinstance(range_start, str) and range_start in record:
            if strategy_name == "date_before_related_field":
                record[field_name] = _relative_temporal_value(record[range_start], field, days=-1)
            else:
                record[field_name] = _relative_temporal_value(record[range_start], field, days=7)
            continue

        numeric_minimum = dependencies.get("maxFor")
        if isinstance(numeric_minimum, str) and numeric_minimum in record:
            if strategy_name == "numeric_max_below_min":
                record[field_name] = _relative_numeric_value(record[numeric_minimum], field, offset=-1)
            else:
                record[field_name] = _valid_numeric_max_value(record[numeric_minimum], field)


def _different_value(value: Any, field: Field) -> Any:
    if value is None:
        return _bounded_text(field, "mismatch")
    if isinstance(value, bool):
        return not value
    if isinstance(value, int) and not isinstance(value, bool):
        return value + 1
    if isinstance(value, float):
        return round(value + 1, 2)

    original = str(value)
    candidate = _bounded_text(field, f"{original}_mismatch", filler="X")
    if candidate != original:
        return candidate
    if not original:
        return _bounded_text(field, "mismatch")
    replacement = "X" if original[-1] != "X" else "Y"
    return f"{original[:-1]}{replacement}"


def _relative_temporal_value(value: Any, field: Field, *, days: int) -> str:
    parsed = _parse_temporal_value(value) or datetime(2026, 1, 1, 9, 0, 0)
    shifted = parsed + timedelta(days=days)
    if field.get("dataType") == "datetime":
        return f"{shifted.isoformat()}Z"
    return shifted.date().isoformat()


def _parse_temporal_value(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None

    normalized = value.removesuffix("Z")
    try:
        if "T" in normalized:
            return datetime.fromisoformat(normalized)
        return datetime.combine(date.fromisoformat(normalized), time(hour=9))
    except ValueError:
        return None


def _valid_numeric_max_value(value: Any, field: Field) -> int | float:
    base = _number_value(value)
    if base is None:
        base = _numeric_minimum(field)

    step = _numeric_step(field)
    candidate = base + step
    constraints = field.get("constraints", {})
    maximum = constraints.get("maximum")
    if isinstance(maximum, (int, float)) and not isinstance(maximum, bool) and candidate > maximum >= base:
        candidate = maximum
    elif isinstance(maximum, (int, float)) and not isinstance(maximum, bool) and maximum < base:
        candidate = base

    minimum = constraints.get("minimum")
    if isinstance(minimum, (int, float)) and not isinstance(minimum, bool) and candidate < minimum:
        candidate = minimum

    return _coerce_number_for_field(candidate, field)


def _relative_numeric_value(value: Any, field: Field, *, offset: int | float) -> int | float:
    base = _number_value(value)
    if base is None:
        base = _numeric_minimum(field)
    return _coerce_number_for_field(base + (offset * _numeric_step(field)), field)


def _number_value(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _numeric_step(field: Field) -> int | float:
    constraints = field.get("constraints", {})
    step = constraints.get("step") or constraints.get("multipleOf")
    if isinstance(step, (int, float)) and not isinstance(step, bool) and step > 0:
        return step
    return 1


def _integer_minimum(field: Field) -> int:
    return int(_numeric_minimum(field))


def _numeric_minimum(field: Field) -> int | float:
    minimum = field.get("constraints", {}).get("minimum")
    if isinstance(minimum, (int, float)) and not isinstance(minimum, bool):
        return minimum
    return 1


def _coerce_number_for_field(value: int | float, field: Field) -> int | float:
    if field.get("dataType") == "integer":
        return int(value)
    return round(float(value), 2)


def _bounded_text(field: Field, value: str, *, filler: str = "x") -> str:
    constraints = field.get("constraints", {})
    minimum = constraints.get("minLength")
    maximum = constraints.get("maxLength")
    if isinstance(maximum, int) and maximum >= 0 and len(value) > maximum:
        value = value[:maximum]
    if isinstance(minimum, int) and len(value) < minimum:
        value = value + (filler * (minimum - len(value)))
    return value


def _bounded_email(field: Field, value: str) -> str:
    constraints = field.get("constraints", {})
    minimum = constraints.get("minLength")
    maximum = constraints.get("maxLength")
    if isinstance(maximum, int) and 5 <= maximum < len(value):
        value = "a@b.c" if maximum < len("a@example.test") else "a@example.test"
    if isinstance(minimum, int) and len(value) < minimum:
        value = f"{'a' * (minimum - len('@example.test'))}@example.test"
    return value


def _bounded_url(field: Field, value: str) -> str:
    constraints = field.get("constraints", {})
    minimum = constraints.get("minLength")
    maximum = constraints.get("maxLength")
    if isinstance(maximum, int) and len("https://a.test") <= maximum < len(value):
        value = "https://a.test"
    if isinstance(minimum, int) and len(value) < minimum:
        value = f"https://{'a' * (minimum - len('https://.test'))}.test"
    return value


def _bounded_domain(field: Field, value: str) -> str:
    constraints = field.get("constraints", {})
    minimum = constraints.get("minLength")
    maximum = constraints.get("maxLength")
    if isinstance(maximum, int) and len("a.test") <= maximum < len(value):
        value = "a.test"
    if isinstance(minimum, int) and len(value) < minimum:
        value = f"{'a' * (minimum - len('.test'))}.test"
    return value


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
    "invalid_phone_format": _invalid_phone_format,
    "valid_country_code": _valid_country_code,
    "valid_address_line": _valid_address_line,
    "valid_city": _valid_city,
    "valid_state": _valid_state,
    "valid_postal_code": _valid_postal_code,
    "valid_country": _valid_country,
    "invalid_alpha": _invalid_alpha,
    "valid_password": _valid_password,
    "weak_password": _weak_password,
    "valid_integer": _valid_integer,
    "valid_decimal": _valid_decimal,
    "valid_enum": _valid_enum,
    "valid_date": _valid_date,
    "valid_time": _valid_time,
    "valid_datetime": _valid_datetime,
    "valid_boolean": _valid_boolean,
    "boolean_false": _boolean_false,
    "boolean_true": _boolean_true,
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
    "xss_payload": _xss_payload,
    "sql_injection_payload": _sql_injection_payload,
    "null_value": _null_value,
    "empty_string": _empty_string,
    "whitespace_only": _whitespace_only,
    "over_max_length": _over_max_length,
    "below_min_length": _below_min_length,
    "duplicate_value": _duplicate_value,
}
