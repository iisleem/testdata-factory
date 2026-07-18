from __future__ import annotations

from copy import deepcopy
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

    if _matches(candidate, text, signals, words={"address", "address line", "street", "street address"}, autocomplete={"street-address", "address-line1", "address-line2"}):
        return _field(candidate, "string", "address_line", 0.82, signals)

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
    scenarios.extend(_security_scenarios(fields))
    scenarios.extend(_robustness_scenarios(fields))
    scenarios.extend(_boundary_scenarios(fields))
    scenarios.extend(_cross_field_scenarios(fields))
    return scenarios


def scenario_strategy(field: dict[str, Any]) -> str:
    dependencies = field.get("dependencies", {})
    if isinstance(dependencies, dict):
        if dependencies.get("matchesField"):
            return "match_field"
        if dependencies.get("rangeEndFor"):
            return "range_end_after_start"
        if dependencies.get("maxFor"):
            return "numeric_max_at_or_above_min"

    business_type = str(field["businessType"])
    if business_type == "enum" and not field.get("constraints", {}).get("values"):
        return "valid_free_text"
    return DEFAULT_STRATEGIES.get(business_type, "valid_free_text")


def annotate_cross_field_dependencies(fields: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    annotated = {field_name: deepcopy(field) for field_name, field in fields.items()}
    _annotate_password_confirmation_dependencies(annotated)
    _annotate_date_range_dependencies(annotated)
    _annotate_numeric_pair_dependencies(annotated)
    return annotated


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


def _security_scenarios(fields: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    security_fields = _text_payload_fields(fields)
    if not security_fields:
        return []
    return [
        _scenario(
            "xss_payloads",
            "security",
            "Text-like fields contain a common reflected XSS probe.",
            {field_name: {"strategy": "xss_payload"} for field_name in security_fields},
        ),
        _scenario(
            "sql_injection_payloads",
            "security",
            "Text-like fields contain a common SQL injection probe.",
            {field_name: {"strategy": "sql_injection_payload"} for field_name in security_fields},
        ),
    ]


def _robustness_scenarios(fields: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []

    null_fields = {
        field_name: {"strategy": "null_value"}
        for field_name, field in fields.items()
        if field.get("required") is True
    }
    if null_fields:
        scenarios.append(
            _scenario(
                "null_required_fields",
                "negative",
                "Required fields are explicitly set to null.",
                null_fields,
            )
        )

    empty_fields = {field_name: {"strategy": "empty_string"} for field_name in _string_like_fields(fields)}
    if empty_fields:
        scenarios.append(
            _scenario(
                "empty_string_fields",
                "negative",
                "String-like fields are submitted as empty strings.",
                empty_fields,
            )
        )

    whitespace_fields = {field_name: {"strategy": "whitespace_only"} for field_name in _string_like_fields(fields)}
    if whitespace_fields:
        scenarios.append(
            _scenario(
                "whitespace_only_fields",
                "negative",
                "String-like fields contain only whitespace.",
                whitespace_fields,
            )
        )

    below_min_length_fields = {
        field_name: {"strategy": "below_min_length"}
        for field_name, field in fields.items()
        if _positive_int_constraint(field, "minLength")
    }
    if below_min_length_fields:
        scenarios.append(
            _scenario(
                "below_min_length_fields",
                "negative",
                "String fields are one character below their minimum length.",
                below_min_length_fields,
            )
        )

    over_max_length_fields = {
        field_name: {"strategy": "over_max_length"}
        for field_name, field in fields.items()
        if isinstance(field.get("constraints", {}).get("maxLength"), int)
    }
    if over_max_length_fields:
        scenarios.append(
            _scenario(
                "over_max_length_fields",
                "negative",
                "String fields are one character over their maximum length.",
                over_max_length_fields,
            )
        )

    unique_fields = {
        field_name: {"strategy": "duplicate_value"}
        for field_name, field in fields.items()
        if field.get("constraints", {}).get("unique") is True
    }
    if unique_fields:
        scenarios.append(
            _scenario(
                "duplicate_unique_fields",
                "negative",
                "Fields marked unique use duplicate values across generated records.",
                unique_fields,
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
    boolean_fields = _boolean_boundary_fields(fields)

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
    if boolean_fields:
        scenarios.append(
            _scenario(
                "boolean_false_boundaries",
                "boundary",
                "Boolean fields use false explicitly.",
                {field_name: {"strategy": "boolean_false", "value": False} for field_name in boolean_fields},
            )
        )
        scenarios.append(
            _scenario(
                "boolean_true_boundaries",
                "boundary",
                "Boolean fields use true explicitly.",
                {field_name: {"strategy": "boolean_true", "value": True} for field_name in boolean_fields},
            )
        )
    return scenarios


def _cross_field_scenarios(fields: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []

    confirmation_fields = {
        field_name: {"strategy": "match_field"}
        for field_name, field in fields.items()
        if isinstance(field.get("dependencies", {}).get("matchesField"), str)
    }
    if confirmation_fields:
        scenarios.append(
            _scenario(
                "matching_confirmation_fields",
                "positive",
                "Confirmation fields match their source fields.",
                confirmation_fields,
            )
        )
        scenarios.append(
            _scenario(
                "mismatched_confirmation_fields",
                "negative",
                "Confirmation fields intentionally differ from their source fields.",
                {field_name: {"strategy": "mismatch_field"} for field_name in confirmation_fields},
            )
        )

    date_range_fields = {
        field_name: {"strategy": "range_end_after_start"}
        for field_name, field in fields.items()
        if isinstance(field.get("dependencies", {}).get("rangeEndFor"), str)
    }
    if date_range_fields:
        scenarios.append(
            _scenario(
                "valid_date_ranges",
                "positive",
                "Date range end fields occur after their start fields.",
                date_range_fields,
            )
        )
        scenarios.append(
            _scenario(
                "invalid_date_ranges",
                "negative",
                "Date range end fields occur before their start fields.",
                {field_name: {"strategy": "date_before_related_field"} for field_name in date_range_fields},
            )
        )

    numeric_pair_fields = {
        field_name: {"strategy": "numeric_max_at_or_above_min"}
        for field_name, field in fields.items()
        if isinstance(field.get("dependencies", {}).get("maxFor"), str)
    }
    if numeric_pair_fields:
        scenarios.append(
            _scenario(
                "valid_numeric_ranges",
                "positive",
                "Numeric maximum fields are at or above their minimum fields.",
                numeric_pair_fields,
            )
        )
        scenarios.append(
            _scenario(
                "invalid_numeric_ranges",
                "negative",
                "Numeric maximum fields are below their minimum fields.",
                {field_name: {"strategy": "numeric_max_below_min"} for field_name in numeric_pair_fields},
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


def _boolean_boundary_fields(fields: dict[str, dict[str, Any]]) -> list[str]:
    return [
        field_name
        for field_name, field in fields.items()
        if field.get("dataType") == "boolean" or field.get("businessType") == "boolean"
    ]


def _text_payload_fields(fields: dict[str, dict[str, Any]]) -> list[str]:
    return [
        field_name
        for field_name, field in fields.items()
        if field.get("dataType") == "string" and field.get("businessType") != "enum"
    ]


def _string_like_fields(fields: dict[str, dict[str, Any]]) -> list[str]:
    return [
        field_name
        for field_name, field in fields.items()
        if field.get("dataType") in {"string", "date", "datetime", "time", "enum"}
    ]


def _positive_int_constraint(field: dict[str, Any], constraint_name: str) -> bool:
    value = field.get("constraints", {}).get(constraint_name)
    return isinstance(value, int) and value > 0


def _annotate_password_confirmation_dependencies(fields: dict[str, dict[str, Any]]) -> None:
    password_fields = [
        field_name
        for field_name, field in fields.items()
        if field.get("businessType") == "password"
    ]
    confirmation_fields = [
        field_name
        for field_name in password_fields
        if _has_any_field_word(fields, field_name, {"confirm", "confirmation", "repeat", "retype", "verify"})
    ]
    source_fields = [field_name for field_name in password_fields if field_name not in confirmation_fields]

    for confirmation_field in confirmation_fields:
        source_field = _best_related_field(confirmation_field, source_fields, fields)
        if source_field:
            _set_dependency(
                fields,
                confirmation_field,
                "matchesField",
                source_field,
                f"dependency:matchesField={source_field}",
            )


def _annotate_date_range_dependencies(fields: dict[str, dict[str, Any]]) -> None:
    date_fields = [
        field_name
        for field_name, field in fields.items()
        if field.get("dataType") in {"date", "datetime"} and field.get("businessType") != "date_of_birth"
    ]
    start_fields = [field_name for field_name in date_fields if _date_role(fields, field_name) == "start"]
    end_fields = [field_name for field_name in date_fields if _date_role(fields, field_name) == "end"]

    for start_field in start_fields:
        end_field = _best_related_field(start_field, end_fields, fields)
        if end_field:
            _set_dependency(fields, start_field, "rangeStartFor", end_field, f"dependency:rangeStartFor={end_field}")
            _set_dependency(fields, end_field, "rangeEndFor", start_field, f"dependency:rangeEndFor={start_field}")


def _annotate_numeric_pair_dependencies(fields: dict[str, dict[str, Any]]) -> None:
    numeric_fields = [
        field_name
        for field_name, field in fields.items()
        if field.get("dataType") in {"integer", "decimal"}
    ]
    minimum_fields = [field_name for field_name in numeric_fields if _numeric_role(fields, field_name) == "min"]
    maximum_fields = [field_name for field_name in numeric_fields if _numeric_role(fields, field_name) == "max"]

    for minimum_field in minimum_fields:
        maximum_field = _best_related_field(minimum_field, maximum_fields, fields)
        if maximum_field:
            _set_dependency(fields, minimum_field, "minFor", maximum_field, f"dependency:minFor={maximum_field}")
            _set_dependency(fields, maximum_field, "maxFor", minimum_field, f"dependency:maxFor={minimum_field}")


def _set_dependency(
    fields: dict[str, dict[str, Any]],
    field_name: str,
    dependency_name: str,
    related_field: str,
    signal: str,
) -> None:
    dependencies = dict(fields[field_name].get("dependencies", {}))
    dependencies.setdefault(dependency_name, related_field)
    fields[field_name]["dependencies"] = dependencies

    inference = fields[field_name].get("inference")
    if not isinstance(inference, dict):
        return
    signals = inference.get("signals")
    if not isinstance(signals, list):
        return
    if signal not in signals:
        signals.append(signal)


def _best_related_field(
    source_field: str,
    candidate_fields: list[str],
    fields: dict[str, dict[str, Any]],
) -> str | None:
    if not candidate_fields:
        return None

    source_stem = _relationship_stem(fields, source_field)
    for candidate_field in candidate_fields:
        if candidate_field == source_field:
            continue
        if _relationship_stem(fields, candidate_field) == source_stem:
            return candidate_field

    for candidate_field in candidate_fields:
        if candidate_field != source_field:
            return candidate_field
    return None


def _relationship_stem(fields: dict[str, dict[str, Any]], field_name: str) -> tuple[str, ...]:
    ignored = {
        "confirm",
        "confirmation",
        "repeat",
        "retype",
        "verify",
        "password",
        "start",
        "begin",
        "beginning",
        "from",
        "end",
        "finish",
        "finished",
        "to",
        "date",
        "time",
        "at",
        "min",
        "minimum",
        "lower",
        "least",
        "max",
        "maximum",
        "upper",
        "most",
    }
    tokens = [token for token in _field_tokens(fields, field_name) if token not in ignored]
    return tuple(tokens)


def _date_role(fields: dict[str, dict[str, Any]], field_name: str) -> str | None:
    text = _field_text(fields, field_name)
    tokens = set(_field_tokens(fields, field_name))
    if {"start", "begin", "beginning", "from", "arrival"} & tokens or "check in" in text or "checkin" in text:
        return "start"
    if {"end", "finish", "finished", "to", "return", "departure"} & tokens or "check out" in text or "checkout" in text:
        return "end"
    return None


def _numeric_role(fields: dict[str, dict[str, Any]], field_name: str) -> str | None:
    tokens = set(_field_tokens(fields, field_name))
    if {"min", "minimum", "lower", "least"} & tokens:
        return "min"
    if {"max", "maximum", "upper", "most"} & tokens:
        return "max"
    return None


def _has_any_field_word(fields: dict[str, dict[str, Any]], field_name: str, words: set[str]) -> bool:
    return bool(set(_field_tokens(fields, field_name)) & words)


def _field_text(fields: dict[str, dict[str, Any]], field_name: str) -> str:
    field = fields[field_name]
    values = [field_name, str(field.get("label", ""))]
    return _split_words(" ".join(value for value in values if value)).lower()


def _field_tokens(fields: dict[str, dict[str, Any]], field_name: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _field_text(fields, field_name))


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
