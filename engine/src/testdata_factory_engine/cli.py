from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .contracts import ContractValidationError, load_contract
from .generation import GenerationError, generate_records


MODEL_PROFILES = {
    "light": {
        "accuracy": "lower",
        "hardware": "low",
        "examples": ["qwen3:4b", "llama3.2:3b", "phi4-mini"],
    },
    "balanced": {
        "accuracy": "medium",
        "hardware": "moderate",
        "examples": ["qwen3:14b", "mistral-nemo", "gemma3:12b"],
    },
    "strong": {
        "accuracy": "high",
        "hardware": "high",
        "examples": ["qwen3:32b", "deepseek-r1:32b", "gemma3:27b"],
    },
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return int(args.command(args))
    except (ContractValidationError, GenerationError, OSError, json.JSONDecodeError) as exc:
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
    validate_command.set_defaults(command=_validate)

    generate_command = subcommands.add_parser("generate", help="Generate test data from a contract scenario.")
    generate_command.add_argument("--contract", required=True, help="Path to a .tdf.json contract.")
    generate_command.add_argument("--scenario", required=True, help="Scenario id to generate.")
    generate_command.add_argument("--count", type=int, default=1, help="Number of records to generate.")
    generate_command.add_argument("--seed", help="Override the contract default seed.")
    generate_command.set_defaults(command=_generate)

    models_command = subcommands.add_parser("models", help="Inspect local model setup.")
    model_subcommands = models_command.add_subparsers(dest="models_command_name", required=True)
    doctor_command = model_subcommands.add_parser("doctor", help="Show supported local model profiles.")
    doctor_command.set_defaults(command=_models_doctor)

    return parser


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
    contract = load_contract(args.contract)
    print(f"Valid contract: {contract.id}")
    return 0


def _generate(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    records = generate_records(contract, args.scenario, count=args.count, seed=args.seed)
    print(json.dumps(records, indent=2))
    return 0


def _models_doctor(args: argparse.Namespace) -> int:
    print(json.dumps({"profiles": MODEL_PROFILES}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
