from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


class ContractValidationError(ValueError):
    """Raised when a contract does not match the TestData Factory schema."""


@dataclass(frozen=True)
class Contract:
    path: Path
    data: dict[str, Any]

    @property
    def id(self) -> str:
        return str(self.data["id"])


def default_schema_path() -> Path:
    return Path(__file__).resolve().parents[3] / "specs" / "contract-schema" / "tdf-contract.schema.json"


def load_json(path: str | Path) -> dict[str, Any]:
    resolved = Path(path)
    with resolved.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ContractValidationError(f"Expected JSON object in {resolved}")
    return data


def load_schema(schema_path: str | Path | None = None) -> dict[str, Any]:
    return load_json(schema_path or default_schema_path())


def validate_contract_data(data: dict[str, Any], schema: dict[str, Any] | None = None) -> None:
    validator = Draft202012Validator(schema or load_schema())
    errors = sorted(validator.iter_errors(data), key=lambda error: list(error.path))
    if errors:
        raise ContractValidationError(_format_validation_error(errors[0]))


def load_contract(path: str | Path, schema_path: str | Path | None = None) -> Contract:
    resolved = Path(path)
    data = load_json(resolved)
    validate_contract_data(data, load_schema(schema_path))
    return Contract(path=resolved, data=data)


def _format_validation_error(error: ValidationError) -> str:
    location = ".".join(str(part) for part in error.absolute_path)
    if not location:
        location = "<root>"
    return f"{location}: {error.message}"
