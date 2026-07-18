from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .generation import DEFAULT_STRATEGIES


@dataclass(frozen=True)
class FieldCandidate:
    name: str = ""
    label: str = ""
    input_type: str = ""
    placeholder: str = ""
    autocomplete: str = ""
    selector: str = ""
    required: bool = False
    constraints: dict[str, Any] = field(default_factory=dict)
    options: list[str] = field(default_factory=list)


def infer_field(candidate: FieldCandidate) -> dict[str, Any]:
    signals: list[str] = []
    text = _candidate_text(candidate)

    if candidate.options:
        return _field(candidate, "enum", "enum", 0.95, ["select options"], {"values": candidate.options})

    if _matches(candidate, text, signals, words={"confirm password", "password confirmation", "repeat password"}):
        return _field(candidate, "string", "password", 0.95, signals)

    if _matches(candidate, text, signals, input_types={"email"}, words={"email", "e-mail"}, autocomplete={"email"}):
        return _field(candidate, "string", "email", 0.95, signals, {"format": "email"})

    if _matches(
        candidate,
        text,
        signals,
        input_types={"tel"},
        words={"phone", "mobile", "telephone", "cell", "cell phone", "tel", "mobile number"},
        autocomplete={"tel", "tel-national"},
    ):
        return _field(candidate, "string", "phone_number", 0.9, signals)

    if _matches(candidate, text, signals, input_types={"password"}, words={"password", "passcode"}):
        return _field(candidate, "string", "password", 0.95, signals)

    if _matches(candidate, text, signals, words={"first name", "firstname"}, autocomplete={"given-name"}):
        return _field(candidate, "string", "first_name", 0.9, signals)

    if _matches(candidate, text, signals, words={"last name", "lastname", "surname"}, autocomplete={"family-name"}):
        return _field(candidate, "string", "last_name", 0.9, signals)

    if _matches(
        candidate,
        text,
        signals,
        words={"full name", "fullname", "display name", "contact name"},
        autocomplete={"name"},
    ):
        return _field(candidate, "string", "full_name", 0.82, signals)

    if _is_bare_name_candidate(candidate):
        signals.append("text:name")
        return _field(candidate, "string", "full_name", 0.82, signals)

    if _matches(candidate, text, signals, words={"username", "user name", "login", "login id", "user id"}):
        return _field(candidate, "string", "username", 0.82, signals)

    if _matches(candidate, text, signals, words={"expiry", "expiration", "expiry date", "expiration date"}):
        return _field(candidate, "string", "expiry_date", 0.84, signals)

    if _matches(
        candidate,
        text,
        signals,
        input_types={"date"},
        words={"birth date", "date of birth", "dob", "birthdate", "birthday", "date"},
    ):
        business_type = "date_of_birth" if any(word in text for word in ["birth", "dob"]) else "date"
        return _field(candidate, "date", business_type, 0.88, signals, {"format": "date"})

    if _matches(candidate, text, signals, input_types={"checkbox"}, words={"agree", "consent", "terms", "enabled", "active", "newsletter", "opt in", "opt-in"}):
        return _field(candidate, "boolean", "boolean", 0.85, signals)

    if _matches(candidate, text, signals, words={"amount", "price", "cost", "total", "balance", "spend", "spending", "limit"}):
        return _field(candidate, "decimal", "amount", 0.82, signals)

    if _matches(candidate, text, signals, words={"currency"}):
        return _field(candidate, "string", "currency", 0.82, signals)

    if _matches(candidate, text, signals, words={"percent", "percentage", "rate"}):
        return _field(candidate, "decimal", "percentage", 0.82, signals)

    if _matches(candidate, text, signals, input_types={"number"}, words={"quantity", "qty", "count", "number of"}):
        return _field(candidate, "integer", "quantity", 0.8, signals)

    if candidate.input_type == "number":
        return _field(candidate, "decimal", "decimal", 0.68, ["input[type=number]"])

    if _matches(candidate, text, signals, words={"address", "address line", "street", "street address"}, autocomplete={"street-address", "address-line1", "address-line2"}):
        return _field(candidate, "string", "address_line", 0.82, signals)

    if _matches(candidate, text, signals, words={"city"}, autocomplete={"address-level2"}):
        return _field(candidate, "string", "city", 0.82, signals)

    if _matches(candidate, text, signals, words={"state", "province"}, autocomplete={"address-level1"}):
        return _field(candidate, "string", "state", 0.82, signals)

    if _matches(candidate, text, signals, words={"zip", "postal"}, autocomplete={"postal-code"}):
        return _field(candidate, "string", "postal_code", 0.82, signals)

    if _matches(candidate, text, signals, words={"country code", "countrycode"}, autocomplete={"country"}):
        return _field(candidate, "string", "country_code", 0.82, signals)

    if _matches(candidate, text, signals, words={"country"}, autocomplete={"country-name"}):
        return _field(candidate, "string", "country", 0.82, signals)

    if _matches(candidate, text, signals, input_types={"url"}, words={"url", "website", "web site", "link"}):
        return _field(candidate, "string", "url", 0.86, signals, {"format": "uri"})

    if _matches(candidate, text, signals, words={"domain", "hostname", "host name"}):
        return _field(candidate, "string", "domain", 0.84, signals)

    if _matches(candidate, text, signals, words={"uuid", "guid", "profile id", "customer id", "external id", "identifier"}):
        return _field(candidate, "string", "uuid", 0.84, signals, {"format": "uuid"})

    if _matches(candidate, text, signals, words={"account number", "acct number", "account no"}):
        return _field(candidate, "string", "account_number", 0.84, signals)

    if _matches(candidate, text, signals, words={"iban"}):
        return _field(candidate, "string", "iban", 0.9, signals)

    if _matches(candidate, text, signals, words={"credit card", "card number", "payment card"}):
        return _field(candidate, "string", "credit_card_number", 0.86, signals)

    if _matches(candidate, text, signals, words={"cvv", "cvc", "security code", "card security code"}):
        return _field(candidate, "string", "cvv", 0.86, signals)

    if _matches(candidate, text, signals, words={"otp", "one time password", "verification code", "security code", "auth code"}):
        return _field(candidate, "string", "otp", 0.84, signals)

    if _matches(candidate, text, signals, words={"tax id", "tax identifier", "tin", "ein"}):
        return _field(candidate, "string", "tax_id", 0.84, signals)

    if _matches(candidate, text, signals, words={"national id", "ssn", "social security", "government id"}):
        return _field(candidate, "string", "national_id", 0.84, signals)

    if _matches(candidate, text, signals, words={"passport", "passport number"}):
        return _field(candidate, "string", "passport_number", 0.84, signals)

    return _field(candidate, "string", "free_text", 0.4, ["fallback: free text"])


def draft_scenarios(
    fields: dict[str, dict[str, Any]],
    *,
    positive_id: str,
    positive_description: str,
) -> list[dict[str, Any]]:
    scenarios = [
        {
            "id": positive_id,
            "kind": "positive",
            "description": positive_description,
            "fields": {
                field_name: {"strategy": scenario_strategy(field)}
                for field_name, field in fields.items()
            },
        }
    ]

    scenarios.extend(_negative_scenarios(fields))
    scenarios.extend(_boundary_scenarios(fields))
    return scenarios


def scenario_strategy(field: dict[str, Any]) -> str:
    business_type = str(field["businessType"])
    if business_type == "enum" and not field.get("constraints", {}).get("values"):
        return "valid_free_text"
    return DEFAULT_STRATEGIES.get(business_type, "valid_free_text")


def _negative_scenarios(fields: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []

    for business_type, scenario_id, strategy, description in (
        ("email", "invalid_email_format", "invalid_email_format", "Email field contains an invalid address."),
        ("phone_number", "invalid_phone_format", "invalid_phone_format", "Phone field contains an invalid number."),
        ("password", "weak_password", "weak_password", "Password field contains an obviously weak value."),
    ):
        field_name = _first_field_with_business_type(fields, business_type)
        if field_name:
            scenarios.append(_scenario(scenario_id, "negative", description, {field_name: {"strategy": strategy}}))

    required_fields = {
        field_name: {"strategy": "missing_required"}
        for field_name, field in fields.items()
        if field.get("required") is True
    }
    if required_fields:
        scenarios.append(
            _scenario(
                "missing_required_fields",
                "negative",
                "Required fields are omitted from the payload.",
                required_fields,
            )
        )

    return scenarios


def _boundary_scenarios(fields: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []
    min_length_fields = _string_boundary_fields(fields, "minLength")
    max_length_fields = _string_boundary_fields(fields, "maxLength")
    minimum_fields = _numeric_boundary_fields(fields, "minimum")
    maximum_fields = _numeric_boundary_fields(fields, "maximum")
    enum_fields = _enum_boundary_fields(fields)
    date_fields = _date_boundary_fields(fields)

    if min_length_fields:
        scenarios.append(
            _scenario(
                "min_length_boundaries",
                "boundary",
                "String fields use values at their minimum allowed length.",
                min_length_fields,
            )
        )
    if max_length_fields:
        scenarios.append(
            _scenario(
                "max_length_boundaries",
                "boundary",
                "String fields use values at their maximum allowed length.",
                max_length_fields,
            )
        )
    if minimum_fields:
        scenarios.append(
            _scenario(
                "numeric_minimum_boundaries",
                "boundary",
                "Numeric fields use their minimum allowed values.",
                minimum_fields,
            )
        )
    if maximum_fields:
        scenarios.append(
            _scenario(
                "numeric_maximum_boundaries",
                "boundary",
                "Numeric fields use their maximum allowed values.",
                maximum_fields,
            )
        )
    if enum_fields:
        scenarios.append(
            _scenario(
                "enum_value_boundaries",
                "boundary",
                "Enum fields use a stable explicit allowed value.",
                enum_fields,
            )
        )
    if date_fields:
        scenarios.append(
            _scenario(
                "date_boundaries",
                "boundary",
                "Date-like fields use explicit boundary values.",
                date_fields,
            )
        )
    return scenarios


def _scenario(
    scenario_id: str,
    kind: str,
    description: str,
    fields: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": scenario_id,
        "kind": kind,
        "description": description,
        "fields": fields,
    }


def _first_field_with_business_type(fields: dict[str, dict[str, Any]], business_type: str) -> str | None:
    for field_name, field in fields.items():
        if field.get("businessType") == business_type:
            return field_name
    return None


def _string_boundary_fields(fields: dict[str, dict[str, Any]], constraint_name: str) -> dict[str, dict[str, Any]]:
    scenario_fields: dict[str, dict[str, Any]] = {}
    for field_name, field in fields.items():
        constraints = field.get("constraints", {})
        length = constraints.get(constraint_name)
        if not isinstance(length, int) or length < 0:
            continue
        value = _string_value_at_length(field, length)
        if value is not None:
            scenario_fields[field_name] = {"strategy": scenario_strategy(field), "value": value}
    return scenario_fields


def _numeric_boundary_fields(fields: dict[str, dict[str, Any]], constraint_name: str) -> dict[str, dict[str, Any]]:
    scenario_fields: dict[str, dict[str, Any]] = {}
    for field_name, field in fields.items():
        constraints = field.get("constraints", {})
        value = constraints.get(constraint_name)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        if field.get("dataType") == "integer" and isinstance(value, float) and value.is_integer():
            value = int(value)
        scenario_fields[field_name] = {"strategy": scenario_strategy(field), "value": value}
    return scenario_fields


def _enum_boundary_fields(fields: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    scenario_fields: dict[str, dict[str, Any]] = {}
    for field_name, field in fields.items():
        values = field.get("constraints", {}).get("values")
        if isinstance(values, list) and values:
            scenario_fields[field_name] = {"strategy": scenario_strategy(field), "value": values[0]}
    return scenario_fields


def _date_boundary_fields(fields: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    scenario_fields: dict[str, dict[str, Any]] = {}
    for field_name, field in fields.items():
        if field.get("dataType") not in {"date", "datetime"}:
            continue
        constraints = field.get("constraints", {})
        value = constraints.get("minimum") or constraints.get("min") or constraints.get("example")
        if isinstance(value, str) and value:
            scenario_fields[field_name] = {"strategy": scenario_strategy(field), "value": value}
    return scenario_fields


def _string_value_at_length(field: dict[str, Any], length: int) -> str | None:
    business_type = str(field.get("businessType", "free_text"))
    constraints = field.get("constraints", {})
    if length == 0:
        return ""
    if business_type == "email":
        if length == 5:
            return "a@b.c"
        return _fit_string("a@b.co", length, filler="x", suffix="@example.test")
    if business_type == "password":
        return _fit_string("Tdf!0000Pass", length, filler="A")
    if business_type == "phone_number":
        return _fit_string("+1555010000", length, filler="0")
    if business_type == "url":
        return _fit_string("https://a.test", length, filler="x", suffix=".test")
    if business_type == "domain":
        return _fit_string("a.test", length, filler="x", suffix=".test")
    if business_type == "uuid":
        return "00000000-0000-4000-8000-000000000000" if length == 36 else None
    if business_type == "currency":
        return "USD" if length == 3 else _fit_string("USD", length, filler="X")
    if business_type == "cvv":
        return "0" * max(length, 3) if length <= 4 else None
    if business_type == "otp":
        return "0" * length
    if business_type == "expiry_date":
        return "01/30" if length == 5 else None

    pattern = constraints.get("pattern")
    if isinstance(pattern, str) and pattern.startswith("https://"):
        return _fit_string("https://a.test", length, filler="x", suffix=".test")
    return "A" * length


def _fit_string(base: str, length: int, *, filler: str, suffix: str = "") -> str | None:
    if len(base) == length:
        return base
    if len(base) > length:
        return None
    if suffix and len(base) + len(suffix) <= length:
        return base[:1] + (filler * (length - len(base[:1]) - len(suffix))) + suffix
    return base + (filler * (length - len(base)))


def _field(
    candidate: FieldCandidate,
    data_type: str,
    business_type: str,
    confidence: float,
    signals: list[str],
    extra_constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    constraints = dict(candidate.constraints)
    if extra_constraints:
        constraints.update(extra_constraints)

    value: dict[str, Any] = {
        "dataType": data_type,
        "businessType": business_type,
        "required": candidate.required,
        "inference": {
            "confidence": confidence,
            "signals": signals,
        },
    }
    if candidate.selector:
        value["selector"] = candidate.selector
    if candidate.label:
        value["label"] = candidate.label
    if constraints:
        value["constraints"] = constraints
    return value


def _candidate_text(candidate: FieldCandidate) -> str:
    parts = [candidate.name, candidate.label, candidate.placeholder, candidate.autocomplete]
    return " ".join(_split_words(part).lower() for part in parts if part)


def _is_bare_name_candidate(candidate: FieldCandidate) -> bool:
    values = [candidate.name, candidate.label, candidate.placeholder]
    return any(_split_words(value).strip().lower() == "name" for value in values if value)


def _matches(
    candidate: FieldCandidate,
    text: str,
    signals: list[str],
    *,
    input_types: set[str] | None = None,
    words: set[str] | None = None,
    autocomplete: set[str] | None = None,
) -> bool:
    input_type = candidate.input_type.lower()
    autocomplete_value = candidate.autocomplete.lower()

    if input_types and input_type in input_types:
        signals.append(f"input[type={input_type}]")
        return True
    if autocomplete and autocomplete_value in autocomplete:
        signals.append(f"autocomplete={autocomplete_value}")
        return True
    if words:
        for word in words:
            normalized = word.lower().replace("_", " ").replace("-", " ")
            if _text_contains(text, normalized):
                signals.append(f"text:{word}")
                return True
    return False


def _split_words(value: str) -> str:
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    return value.replace("_", " ").replace("-", " ")


def _text_contains(text: str, phrase: str) -> bool:
    if " " in phrase:
        return phrase in text
    return re.search(rf"\b{re.escape(phrase)}\b", text) is not None
