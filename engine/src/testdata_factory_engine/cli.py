from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .contracts import ContractValidationError, load_contract, validate_contract_file
from .generation import GenerationError, generate_records
from .models import model_profiles_payload
from .scanner import ScannerError, scan_contract_draft
from .schema_import import SchemaImportError, import_json_schema_contract, import_openapi_request_contract


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return int(args.command(args))
    except (ContractValidationError, GenerationError, ScannerError, SchemaImportError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tdf", description="Generate deterministic test data from TestData Factory contracts.")
    subcommands = parser.add_subparsers(dest="command_name", required=True)

    init_command = subcommands.add_parser("init", help="Create a local TestData Factory config file.")
    init_command.add_argument("--output", default="tdf.config.json", help="Config file path to create.")
    init_command.set_defaults(command=_init)

    validate_command = subcommands.add_parser("validate", help="Validate a .tdf.json contract.")
    validate_command.add_argument("contract", help="Path to a .tdf.json contract.")
    validate_command.add_argument("--json", action="store_true", help="Print structured validation feedback as JSON.")
    validate_command.set_defaults(command=_validate)

    import_command = subcommands.add_parser("import", help="Import a schema as a .tdf.json contract.")
    import_subcommands = import_command.add_subparsers(dest="import_command_name", required=True)

    json_schema_command = import_subcommands.add_parser("json-schema", help="Import JSON Schema object properties.")
    json_schema_command.add_argument("schema", help="Path to a JSON Schema document.")
    json_schema_command.add_argument("--id", help="Contract id. Defaults to the schema title or file name.")
    json_schema_command.add_argument("--out", required=True, help="Path to write the .tdf.json contract.")
    _add_locale_arguments(json_schema_command)
    json_schema_command.set_defaults(command=_import_json_schema)

    openapi_command = import_subcommands.add_parser("openapi", help="Import an OpenAPI operation request schema.")
    openapi_command.add_argument("openapi", help="Path to an OpenAPI JSON document.")
    openapi_command.add_argument("--operation", required=True, help="Operation id or METHOD /path selector.")
    openapi_command.add_argument("--id", help="Contract id. Defaults to the selected operation.")
    openapi_command.add_argument("--out", required=True, help="Path to write the .tdf.json contract.")
    _add_locale_arguments(openapi_command)
    openapi_command.set_defaults(command=_import_openapi)

    generate_command = subcommands.add_parser("generate", help="Generate test data from a contract scenario.")
    generate_command.add_argument("--contract", required=True, help="Path to a .tdf.json contract.")
    generate_command.add_argument("--scenario", required=True, help="Scenario id to generate.")
    generate_command.add_argument("--count", type=int, default=1, help="Number of records to generate.")
    generate_command.add_argument("--seed", help="Override the contract default seed.")
    generate_command.set_defaults(command=_generate)

    scan_command = subcommands.add_parser("scan-url", help="Scan a URL or local HTML form into a contract draft.")
    scan_command.add_argument("source", help="URL or local HTML file path to scan.")
    scan_command.add_argument("--id", dest="contract_id", help="Contract id to use in the draft.")
    scan_command.add_argument("--output", help="Path to write the .tdf.json draft. Defaults to stdout.")
    scan_command.add_argument("--locale-language", default="en", help="Locale language code for the draft.")
    scan_command.add_argument("--locale-country", help="Optional locale country code for the draft.")
    scan_command.set_defaults(command=_scan_url)

    models_command = subcommands.add_parser("models", help="Inspect local model setup.")
    model_subcommands = models_command.add_subparsers(dest="models_command_name", required=True)
    doctor_command = model_subcommands.add_parser("doctor", help="Show supported local model profiles.")
    doctor_command.set_defaults(command=_models_doctor)

    return parser


def _add_locale_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument("--language", default="en", help="Locale language code for the generated contract.")
    command.add_argument("--country", help="Optional two-letter locale country code for the generated contract.")


def _init(args: argparse.Namespace) -> int:
    output = Path(args.output)
    if output.exists():
        raise OSError(f"{output} already exists")

    config = {
        "modelProfile": "balanced",
        "provider": {
            "type": "ollama",
            "baseUrl": "http://localhost:11434",
            "model": "qwen3:14b",
        },
        "generation": {
            "defaultSeed": "local",
            "includeMetadata": False,
        },
    }
    output.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"Created {output}")
    return 0


def _validate(args: argparse.Namespace) -> int:
    result = validate_contract_file(args.contract)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return 0 if result.is_valid else 1

    if result.is_valid:
        contract = load_contract(args.contract)
        if result.status == "needs_review":
            print(f"Contract needs review: {contract.id}")
        else:
            print(f"Valid contract: {contract.id}")
        for finding in result.findings:
            if finding.severity != "info":
                location = finding.field or "<root>"
                print(f"{finding.severity}: {location}: {finding.message}")
        return 0

    for finding in result.findings:
        location = finding.field or "<root>"
        print(f"{finding.severity}: {location}: {finding.message}", file=sys.stderr)
    return 1


def _import_json_schema(args: argparse.Namespace) -> int:
    schema_path = Path(args.schema)
    schema = _load_json(schema_path)
    contract = import_json_schema_contract(
        schema,
        contract_id=args.id or schema_path.stem,
        source_value=str(schema_path),
        locale=_locale(args),
    )
    _write_contract(contract, args.out)
    print(f"Imported contract: {contract['id']}")
    return 0


def _import_openapi(args: argparse.Namespace) -> int:
    openapi_path = Path(args.openapi)
    document = _load_json(openapi_path)
    contract = import_openapi_request_contract(
        document,
        args.operation,
        contract_id=args.id,
        source_value=str(openapi_path),
        locale=_locale(args),
    )
    _write_contract(contract, args.out)
    print(f"Imported contract: {contract['id']}")
    return 0


def _generate(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    records = generate_records(contract, args.scenario, count=args.count, seed=args.seed)
    print(json.dumps(records, indent=2))
    return 0


def _scan_url(args: argparse.Namespace) -> int:
    draft = scan_contract_draft(
        args.source,
        contract_id=args.contract_id,
        locale_language=args.locale_language,
        locale_country=args.locale_country,
    )
    output = json.dumps(draft, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


def _models_doctor(args: argparse.Namespace) -> int:
    print(json.dumps({"profiles": model_profiles_payload()}, indent=2))
    return 0


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise SchemaImportError(f"Expected JSON object in {path}")
    return data


def _locale(args: argparse.Namespace) -> dict[str, str]:
    locale = {"language": str(args.language)}
    if args.country:
        locale["country"] = str(args.country)
    return locale


def _write_contract(contract: dict[str, Any], output: str) -> None:
    output_path = Path(output)
    output_path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
