from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .contracts import validate_contract_data


class SchemaImportError(ValueError):
    """Raised when a schema cannot be imported as a TestData Factory contract."""


HTTP_METHODS = {"delete", "get", "head", "options", "patch", "post", "put", "trace"}
JSON_MEDIA_TYPES = ("application/json",)
CONSTRAINT_KEYS = (
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "pattern",
    "format",
    "minItems",
    "maxItems",
    "uniqueItems",
    "minProperties",
    "maxProperties",
)
METADATA_KEYS = ("description", "examples", "example", "default", "deprecated", "readOnly", "writeOnly")
SCENARIO_STRATEGIES = {
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
}


@dataclass(frozen=True)
class OpenAPIOperation:
    path: str
    method: str
    operation: dict[str, Any]

    @property
    def reference(self) -> str:
        operation_id = self.operation.get("operationId")
        if isinstance(operation_id, str) and operation_id.strip():
            return operation_id.strip()
        return f"{self.method.upper()} {self.path}"


def import_json_schema_contract(
    schema: dict[str, Any],
    *,
    contract_id: str | None = None,
    source_value: str = "json-schema",
    locale: dict[str, str] | None = None,
) -> dict[str, Any]:
    root_schema = _resolve_schema(schema, schema)
    contract = _build_contract(
        contract_id=_contract_id(contract_id or _schema_title(root_schema) or _source_contract_name(source_value)),
        source_type="json_schema",
        source_value=source_value,
        locale=locale,
        fields=_import_object_fields(root_schema, schema, signal_source="json_schema"),
    )
    _validate_imported_contract(contract)
    return contract


def import_openapi_request_contract(
    document: dict[str, Any],
    operation: str,
    *,
    contract_id: str | None = None,
    source_value: str = "openapi",
    locale: dict[str, str] | None = None,
) -> dict[str, Any]:
    selected_operation = _find_openapi_operation(document, operation)
    request_schema = _operation_request_schema(document, selected_operation.operation)
    root_schema = _resolve_schema(document, request_schema)
    contract = _build_contract(
        contract_id=_contract_id(contract_id or selected_operation.reference),
        source_type="openapi",
        source_value=f"{source_value}#{selected_operation.reference}",
        locale=locale,
        fields=_import_object_fields(root_schema, document, signal_source="openapi"),
    )
    _validate_imported_contract(contract)
    return contract


def _validate_imported_contract(contract: dict[str, Any]) -> None:
    result = validate_contract_data(contract)
    if result is None:
        return

    if getattr(result, "is_valid", True) is False or getattr(result, "status", None) == "invalid":
        raise SchemaImportError(_format_validation_result(result))


def _format_validation_result(result: Any) -> str:
    findings = getattr(result, "findings", ())
    messages = [
        f"{getattr(finding, 'field', None) or '<root>'}: {getattr(finding, 'message', 'Invalid contract')}"
        for finding in findings
        if getattr(finding, "severity", "error") == "error"
    ]
    if messages:
        return "Imported contract is invalid: " + "; ".join(messages)
    return "Imported contract is invalid"


def _build_contract(
    *,
    contract_id: str,
    source_type: str,
    source_value: str,
    locale: dict[str, str] | None,
    fields: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    scenario_fields = {field_name: {"strategy": _scenario_strategy(field)} for field_name, field in fields.items()}
    return {
        "schemaVersion": "1.0",
        "id": contract_id,
        "source": {
            "type": source_type,
            "value": source_value,
        },
        "locale": locale or {"language": "en"},
        "fields": fields,
        "scenarios": [
            {
                "id": "valid_payload",
                "kind": "positive",
                "description": "All imported fields contain valid values.",
                "fields": scenario_fields,
            }
        ],
        "generation": {
            "deterministic": True,
            "defaultSeed": f"{contract_id}-suite",
        },
        "validation": {
            "status": "needs_review",
        },
    }


def _import_object_fields(
    schema: dict[str, Any],
    document: dict[str, Any],
    *,
    signal_source: str,
) -> dict[str, dict[str, Any]]:
    properties = schema.get("properties")
    if not isinstance(properties, dict) or not properties:
        raise SchemaImportError("Schema import requires an object schema with properties")

    required = schema.get("required", [])
    required_fields = {str(field) for field in required} if isinstance(required, list) else set()
    fields: dict[str, dict[str, Any]] = {}
    for field_name, property_schema in properties.items():
        if not isinstance(property_schema, dict):
            raise SchemaImportError(f"Property schema must be an object: {field_name}")
        resolved_schema = _resolve_schema(document, property_schema)
        fields[str(field_name)] = _field_from_schema(
            str(field_name),
            resolved_schema,
            required=str(field_name) in required_fields,
            signal_source=signal_source,
        )
    return fields


def _field_from_schema(
    name: str,
    schema: dict[str, Any],
    *,
    required: bool,
    signal_source: str,
) -> dict[str, Any]:
    constraints = _constraints_from_schema(schema)
    data_type, business_type, confidence, reason = _infer_types(name, schema)
    signals = _field_signals(schema, required=required, signal_source=signal_source)
    if reason:
        signals.append(reason)

    field: dict[str, Any] = {
        "label": _field_label(name, schema),
        "dataType": data_type,
        "businessType": business_type,
        "required": required,
        "inference": {
            "confidence": confidence,
            "signals": signals,
        },
    }
    if constraints:
        field["constraints"] = constraints
    return field


def _constraints_from_schema(schema: dict[str, Any]) -> dict[str, Any]:
    constraints: dict[str, Any] = {}
    for key in CONSTRAINT_KEYS:
        if key in schema:
            constraints[key] = schema[key]

    enum_values = schema.get("enum")
    if isinstance(enum_values, list):
        if _values_constraint_supported(enum_values):
            constraints["values"] = enum_values
        else:
            constraints["enum"] = enum_values
            simple_values = [value for value in enum_values if _simple_constraint_value(value)]
            if simple_values:
                constraints["values"] = simple_values

    if "const" in schema:
        constraints["const"] = schema["const"]

    for key in METADATA_KEYS:
        if key in schema:
            constraints[key] = schema[key]

    schema_type = schema.get("type")
    if schema.get("nullable") is True or (isinstance(schema_type, list) and "null" in schema_type):
        constraints["nullable"] = True

    return constraints


def _infer_types(name: str, schema: dict[str, Any]) -> tuple[str, str, float, str | None]:
    data_type = _data_type(schema)
    schema_format = str(schema.get("format", "")).lower()
    text = _search_text(name, schema)

    if isinstance(schema.get("enum"), list):
        return "enum", "enum", 0.95, "schema:enum"
    if schema_format == "email" or _contains(text, "email", "e mail"):
        return "string", "email", 0.95, "schema:email"
    if _contains(text, "phone", "mobile", "telephone", "cell"):
        return "string", "phone_number", 0.9, "schema:name:phone"
    if _contains(text, "password", "passcode"):
        return "string", "password", 0.95, "schema:name:password"
    if _contains(text, "first name", "firstname", "given name"):
        return "string", "first_name", 0.88, "schema:name:first_name"
    if _contains(text, "last name", "lastname", "family name", "surname"):
        return "string", "last_name", 0.88, "schema:name:last_name"
    if _contains(text, "username", "user name", "login"):
        return "string", "username", 0.84, "schema:name:username"
    if text.strip() in {"name", "full name", "fullname"}:
        return "string", "full_name", 0.82, "schema:name:full_name"
    if schema_format == "date":
        business_type = "date_of_birth" if _contains(text, "birth", "date of birth", "dob") else "date"
        return "date", business_type, 0.92, f"schema:format={schema_format}"
    if schema_format == "date-time":
        return "datetime", "datetime", 0.92, f"schema:format={schema_format}"
    if schema_format == "time":
        return "time", "time", 0.92, f"schema:format={schema_format}"
    if schema_format == "uuid":
        return "string", "uuid", 0.92, f"schema:format={schema_format}"
    if schema_format in {"uri", "uri-reference", "url", "iri", "iri-reference"} or _contains(text, "url", "website", "link"):
        return "string", "url", 0.86, "schema:url"
    if schema_format in {"hostname", "idn-hostname"} or _contains(text, "domain", "hostname"):
        return "string", "domain", 0.86, "schema:domain"
    if _contains(text, "amount", "price", "cost", "total", "balance", "spend", "spending"):
        return data_type if data_type in {"integer", "decimal"} else "decimal", "amount", 0.82, "schema:name:amount"
    if _contains(text, "currency"):
        return "string", "currency", 0.82, "schema:name:currency"
    if _contains(text, "percent", "percentage"):
        return data_type if data_type in {"integer", "decimal"} else "decimal", "percentage", 0.82, "schema:name:percentage"
    if _contains(text, "quantity", "count"):
        return "integer" if data_type == "integer" else data_type, "quantity", 0.8, "schema:name:quantity"
    if _contains(text, "address", "street"):
        return "string", "address_line", 0.82, "schema:name:address"
    if _contains(text, "city"):
        return "string", "city", 0.82, "schema:name:city"
    if _contains(text, "state", "province"):
        return "string", "state", 0.82, "schema:name:state"
    if _contains(text, "zip", "postal"):
        return "string", "postal_code", 0.82, "schema:name:postal_code"
    if _contains(text, "country code"):
        return "string", "country_code", 0.82, "schema:name:country_code"
    if _contains(text, "country"):
        return "string", "country", 0.82, "schema:name:country"
    if _contains(text, "tax id", "tin"):
        return "string", "tax_id", 0.82, "schema:name:tax_id"
    if _contains(text, "passport"):
        return "string", "passport_number", 0.82, "schema:name:passport"
    if _contains(text, "national id", "ssn", "social security"):
        return "string", "national_id", 0.82, "schema:name:national_id"
    if _contains(text, "iban"):
        return "string", "iban", 0.82, "schema:name:iban"
    if _contains(text, "account number"):
        return "string", "account_number", 0.82, "schema:name:account_number"
    if _contains(text, "credit card", "card number"):
        return "string", "credit_card_number", 0.82, "schema:name:credit_card_number"
    if _contains(text, "cvv", "cvc"):
        return "string", "cvv", 0.82, "schema:name:cvv"
    if _contains(text, "expiry", "expiration"):
        return "string", "expiry_date", 0.82, "schema:name:expiry_date"
    if _contains(text, "otp", "one time password"):
        return "string", "otp", 0.82, "schema:name:otp"

    if data_type == "integer":
        return data_type, "integer", 0.75, "schema:type=integer"
    if data_type == "decimal":
        return data_type, "decimal", 0.75, "schema:type=number"
    if data_type == "boolean":
        return data_type, "boolean", 0.78, "schema:type=boolean"
    if data_type == "date":
        return data_type, "date", 0.8, "schema:type=date"
    if data_type == "datetime":
        return data_type, "datetime", 0.8, "schema:type=datetime"
    if data_type == "time":
        return data_type, "time", 0.8, "schema:type=time"

    return data_type, "free_text", 0.45, "schema:fallback"


def _data_type(schema: dict[str, Any]) -> str:
    schema_type = _schema_type(schema)
    schema_format = str(schema.get("format", "")).lower()
    if isinstance(schema.get("enum"), list):
        return "enum"
    if schema_type == "integer":
        return "integer"
    if schema_type == "number":
        return "decimal"
    if schema_type == "boolean":
        return "boolean"
    if schema_type == "array":
        return "array"
    if schema_type == "object":
        return "object"
    if schema_type == "string":
        if schema_format == "date":
            return "date"
        if schema_format == "date-time":
            return "datetime"
        if schema_format == "time":
            return "time"
    return "string"


def _schema_type(schema: dict[str, Any]) -> str:
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        for value in schema_type:
            if value != "null":
                return str(value)
        return "string"
    if isinstance(schema_type, str):
        return schema_type
    if "properties" in schema:
        return "object"
    if "items" in schema:
        return "array"
    if isinstance(schema.get("enum"), list):
        return _enum_type(schema["enum"])
    return "string"


def _enum_type(values: list[Any]) -> str:
    for value in values:
        if value is None:
            continue
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "number"
        return "string"
    return "string"


def _field_signals(schema: dict[str, Any], *, required: bool, signal_source: str) -> list[str]:
    signals = [f"{signal_source}:property"]
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        signals.append(f"{signal_source}:type={','.join(str(value) for value in schema_type)}")
    elif isinstance(schema_type, str):
        signals.append(f"{signal_source}:type={schema_type}")
    if isinstance(schema.get("format"), str):
        signals.append(f"{signal_source}:format={schema['format']}")
    if isinstance(schema.get("enum"), list):
        signals.append(f"{signal_source}:enum")
    if required:
        signals.append(f"{signal_source}:required")
    return signals


def _field_label(name: str, schema: dict[str, Any]) -> str:
    title = schema.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return _humanize(name)


def _scenario_strategy(field: dict[str, Any]) -> str:
    business_type = str(field["businessType"])
    if business_type == "enum" and not field.get("constraints", {}).get("values"):
        return "valid_free_text"
    return SCENARIO_STRATEGIES.get(business_type, "valid_free_text")


def _find_openapi_operation(document: dict[str, Any], selector: str) -> OpenAPIOperation:
    matches: list[OpenAPIOperation] = []
    selector_text = selector.strip()
    selector_key = selector_text.lower()
    for path, path_item in _openapi_operations(document):
        for method, operation in path_item:
            operation_id = operation.get("operationId")
            candidates = {
                f"{method.upper()} {path}",
                f"{method.lower()} {path}",
                f"{path} {method.upper()}",
                f"{path} {method.lower()}",
            }
            if isinstance(operation_id, str):
                candidates.add(operation_id)
            if any(selector_text == candidate or selector_key == candidate.lower() for candidate in candidates):
                matches.append(OpenAPIOperation(path=path, method=method, operation=operation))

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise SchemaImportError(f"OpenAPI operation selector is ambiguous: {selector}")

    available = ", ".join(_available_operation_names(document)) or "none"
    raise SchemaImportError(f"OpenAPI operation not found: {selector}. Available operations: {available}")


def _openapi_operations(document: dict[str, Any]) -> list[tuple[str, list[tuple[str, dict[str, Any]]]]]:
    paths = document.get("paths")
    if not isinstance(paths, dict):
        raise SchemaImportError("OpenAPI document must contain a paths object")

    operations: list[tuple[str, list[tuple[str, dict[str, Any]]]]] = []
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        path_operations: list[tuple[str, dict[str, Any]]] = []
        for method, operation in path_item.items():
            method_key = str(method).lower()
            if method_key in HTTP_METHODS and isinstance(operation, dict):
                path_operations.append((method_key, operation))
        if path_operations:
            operations.append((str(path), path_operations))
    return operations


def _available_operation_names(document: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for path, path_item in _openapi_operations(document):
        for method, operation in path_item:
            operation_id = operation.get("operationId")
            if isinstance(operation_id, str) and operation_id.strip():
                names.append(f"{operation_id.strip()} ({method.upper()} {path})")
            else:
                names.append(f"{method.upper()} {path}")
    return names


def _operation_request_schema(document: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
    request_body = operation.get("requestBody")
    if isinstance(request_body, dict) and "$ref" in request_body:
        request_body = _resolve_ref(document, str(request_body["$ref"]))
    if not isinstance(request_body, dict):
        raise SchemaImportError("Selected OpenAPI operation does not define a requestBody")

    content = request_body.get("content")
    if not isinstance(content, dict) or not content:
        raise SchemaImportError("Selected OpenAPI requestBody does not define content")

    media_type = _select_json_media_type(content)
    media = content[media_type]
    if not isinstance(media, dict) or not isinstance(media.get("schema"), dict):
        raise SchemaImportError(f"OpenAPI requestBody media type does not define a schema: {media_type}")
    return media["schema"]


def _select_json_media_type(content: dict[str, Any]) -> str:
    for media_type in JSON_MEDIA_TYPES:
        if media_type in content:
            return media_type
    for media_type in content:
        if str(media_type).endswith("+json"):
            return str(media_type)
    for media_type in content:
        return str(media_type)
    raise SchemaImportError("OpenAPI requestBody content is empty")


def _resolve_schema(document: dict[str, Any], schema: dict[str, Any], seen_refs: tuple[str, ...] = ()) -> dict[str, Any]:
    if "$ref" in schema:
        ref = str(schema["$ref"])
        if ref in seen_refs:
            raise SchemaImportError(f"Circular schema reference: {ref}")
        resolved = _resolve_schema(document, _resolve_ref(document, ref), (*seen_refs, ref))
        siblings = {key: value for key, value in schema.items() if key != "$ref"}
        if siblings:
            return _merge_schemas(resolved, siblings)
        return resolved

    if isinstance(schema.get("allOf"), list):
        merged: dict[str, Any] = {}
        for item in schema["allOf"]:
            if isinstance(item, dict):
                merged = _merge_schemas(merged, _resolve_schema(document, item, seen_refs))
        siblings = {key: value for key, value in schema.items() if key != "allOf"}
        return _merge_schemas(merged, siblings)

    return dict(schema)


def _resolve_ref(document: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise SchemaImportError(f"Only local schema references are supported: {ref}")

    value: Any = document
    for token in ref[2:].split("/"):
        key = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            raise SchemaImportError(f"Schema reference not found: {ref}")
    if not isinstance(value, dict):
        raise SchemaImportError(f"Schema reference must point to an object: {ref}")
    return value


def _merge_schemas(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    for key, value in right.items():
        if key == "properties" and isinstance(value, dict):
            existing = merged.get("properties", {})
            merged["properties"] = {**existing, **value} if isinstance(existing, dict) else dict(value)
        elif key == "required" and isinstance(value, list):
            existing = merged.get("required", [])
            required = list(existing) if isinstance(existing, list) else []
            for item in value:
                if item not in required:
                    required.append(item)
            merged["required"] = required
        else:
            merged[key] = value
    return merged


def _schema_title(schema: dict[str, Any]) -> str | None:
    title = schema.get("title")
    if isinstance(title, str) and title.strip():
        return title
    schema_id = schema.get("$id")
    if isinstance(schema_id, str) and schema_id.strip():
        return schema_id.rstrip("/").rsplit("/", maxsplit=1)[-1]
    return None


def _source_contract_name(source_value: str) -> str:
    source = source_value.split("#", maxsplit=1)[0].split("?", maxsplit=1)[0].rstrip("/\\")
    name = re.split(r"[/\\]", source)[-1]
    if "." in name:
        return name.rsplit(".", maxsplit=1)[0]
    return name or "imported-schema"


def _contract_id(value: str) -> str:
    text = _split_words(value.strip())
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    if not text:
        return "imported-schema"
    if not text[0].isalnum():
        return f"contract-{text}"
    return text


def _humanize(value: str) -> str:
    text = _split_words(value)
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).strip()
    if not text:
        return value
    return text[:1].upper() + text[1:]


def _search_text(name: str, schema: dict[str, Any]) -> str:
    values = [name, schema.get("title"), schema.get("description")]
    return _split_words(" ".join(str(value) for value in values if isinstance(value, str))).lower()


def _split_words(value: str) -> str:
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    return value.replace("_", " ").replace("-", " ")


def _contains(text: str, *phrases: str) -> bool:
    compact_text = text.replace(" ", "")
    for phrase in phrases:
        normalized = _split_words(phrase).lower()
        if normalized in text or normalized.replace(" ", "") in compact_text:
            return True
    return False


def _values_constraint_supported(values: list[Any]) -> bool:
    return all(_simple_constraint_value(value) for value in values)


def _simple_constraint_value(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool)) and value is not None
