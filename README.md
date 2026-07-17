# TestData Factory

Open-source, local-first AI test data generation for automation engineers.

TestData Factory analyzes application forms, page metadata, or explicit contracts, infers field intent, and generates positive, negative, and boundary test data that can be used directly inside Java, TypeScript, and Python automation tests.

## Current Status

This repository is in requirements/design phase.

Primary requirements are documented in:

- [Product Requirements](docs/requirements.md)
- [Local Model Profiles](docs/model-profiles.md)

## Product Direction

The project is library-first, API-optional:

- Java, TypeScript, and Python SDKs for direct use in tests.
- CLI for scanning pages, generating contracts, and producing fixtures.
- Self-hosted API server for teams that want a shared service.
- Local open-weight model support by default.
- Deterministic generation during test execution through contracts and seeds.

The license target is MIT.

The final repository name is `testdata-factory`.

## Development

Current foundation validation:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e 'engine[dev]'
cd engine
python -m pytest
tdf --help
```
