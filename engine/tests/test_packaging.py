from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from testdata_factory_engine.contracts import load_schema


ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "engine"
CONTRACT = ROOT / "examples" / "contracts" / "register.tdf.json"
SPEC_SCHEMA = ROOT / "specs" / "contract-schema" / "tdf-contract.schema.json"


def test_default_schema_resource_matches_contract_schema_spec() -> None:
    expected_schema = json.loads(SPEC_SCHEMA.read_text(encoding="utf-8"))

    assert load_schema() == expected_schema


def test_built_wheel_tdf_validate_uses_packaged_schema(tmp_path: Path) -> None:
    wheel_dir = tmp_path / "wheelhouse"
    wheel_dir.mkdir()
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "--disable-pip-version-check",
            "wheel",
            ".",
            "--no-deps",
            "--wheel-dir",
            wheel_dir,
        ],
        cwd=ENGINE,
    )
    wheel = next(wheel_dir.glob("testdata_factory_engine-*.whl"))

    venv_dir = tmp_path / "venv"
    _run([sys.executable, "-m", "venv", venv_dir])
    bin_dir = "Scripts" if os.name == "nt" else "bin"
    python = venv_dir / bin_dir / ("python.exe" if os.name == "nt" else "python")
    tdf = venv_dir / bin_dir / ("tdf.exe" if os.name == "nt" else "tdf")
    _run([python, "-m", "pip", "--disable-pip-version-check", "install", wheel])

    contract = tmp_path / "register.tdf.json"
    shutil.copyfile(CONTRACT, contract)
    result = _run([tdf, "validate", contract], cwd=tmp_path)

    assert "Valid contract: register" in result.stdout


def _run(command: list[object], **kwargs: object) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(part) for part in command],
        text=True,
        capture_output=True,
        **kwargs,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result
