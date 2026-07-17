from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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

    if _matches(candidate, text, signals, input_types={"email"}, words={"email", "e-mail"}, autocomplete={"email"}):
        return _field(candidate, "string", "email", 0.95, signals, {"format": "email"})

    if _matches(candidate, text, signals, input_types={"tel"}, words={"phone", "mobile", "telephone", "cell"}, autocomplete={"tel"}):
        return _field(candidate, "string", "phone_number", 0.9, signals)

    if _matches(candidate, text, signals, input_types={"password"}, words={"password", "passcode"}):
        return _field(candidate, "string", "password", 0.95, signals)

    if _matches(candidate, text, signals, words={"first name", "firstname"}, autocomplete={"given-name"}):
        return _field(candidate, "string", "first_name", 0.9, signals)

    if _matches(candidate, text, signals, words={"last name", "lastname", "surname"}, autocomplete={"family-name"}):
        return _field(candidate, "string", "last_name", 0.9, signals)

    if _matches(candidate, text, signals, words={"full name", "fullname", "name"}, autocomplete={"name"}):
        return _field(candidate, "string", "full_name", 0.82, signals)

    if _matches(candidate, text, signals, words={"username", "user name", "login"}):
        return _field(candidate, "string", "username", 0.82, signals)

    if _matches(candidate, text, signals, input_types={"date"}, words={"birth date", "date of birth", "dob", "date"}):
        business_type = "date_of_birth" if any(word in text for word in ["birth", "dob"]) else "date"
        return _field(candidate, "date", business_type, 0.88, signals, {"format": "date"})

    if _matches(candidate, text, signals, input_types={"checkbox"}, words={"agree", "enabled", "active", "newsletter"}):
        return _field(candidate, "boolean", "boolean", 0.85, signals)

    if _matches(candidate, text, signals, words={"amount", "price", "cost", "total", "balance"}):
        return _field(candidate, "decimal", "amount", 0.82, signals)

    if _matches(candidate, text, signals, words={"currency"}):
        return _field(candidate, "string", "currency", 0.82, signals)

    if _matches(candidate, text, signals, input_types={"number"}, words={"quantity", "count"}):
        return _field(candidate, "integer", "quantity", 0.8, signals)

    if candidate.input_type == "number":
        return _field(candidate, "decimal", "decimal", 0.68, ["input[type=number]"])

    if _matches(candidate, text, signals, words={"address", "street"}, autocomplete={"street-address", "address-line1"}):
        return _field(candidate, "string", "address_line", 0.82, signals)

    if _matches(candidate, text, signals, words={"city"}, autocomplete={"address-level2"}):
        return _field(candidate, "string", "city", 0.82, signals)

    if _matches(candidate, text, signals, words={"state", "province"}, autocomplete={"address-level1"}):
        return _field(candidate, "string", "state", 0.82, signals)

    if _matches(candidate, text, signals, words={"zip", "postal"}, autocomplete={"postal-code"}):
        return _field(candidate, "string", "postal_code", 0.82, signals)

    if _matches(candidate, text, signals, words={"country"}, autocomplete={"country", "country-name"}):
        return _field(candidate, "string", "country", 0.82, signals)

    if _matches(candidate, text, signals, input_types={"url"}, words={"url", "website", "link"}):
        return _field(candidate, "string", "url", 0.86, signals, {"format": "uri"})

    return _field(candidate, "string", "free_text", 0.4, ["fallback: free text"])


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
    return " ".join(part.lower().replace("_", " ").replace("-", " ") for part in parts if part)


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
            if normalized in text:
                signals.append(f"text:{word}")
                return True
    return False
