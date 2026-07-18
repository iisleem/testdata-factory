# Developer Guide

This guide is for contributors working from the source repository.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `engine/` | Python engine, CLI, scanner, importers, API server, contract validation, generation, and Python SDK. |
| `sdk-java/` | Java SDK source package and tests. |
| `sdk-typescript/` | TypeScript SDK source package and tests. |
| `examples/` | Contracts and import inputs used by the docs. |
| `examples/frameworks/` | Lightweight framework integration examples for automation engineers. |
| `specs/` | Published OpenAPI and contract schema specs. |
| `docs/` | User and developer documentation. |
| `CHANGELOG.md` | Release notes for package-ready changes. |

## Package Metadata

The current release version is `0.1.0`.

- Python engine and CLI: `testdata-factory-engine`
- Java SDK: `io.github.iisleem.testdatafactory:testdata-factory`
- TypeScript SDK: `testdata-factory`

## Python Engine Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e 'engine[dev,server,scanner]'
python -m playwright install chromium
```

Run engine tests:

```bash
python -m pytest engine
```

Run focused tests:

```bash
python -m pytest engine/tests/test_cli.py
python -m pytest engine/tests/test_server.py
python -m pytest engine/tests/test_schema_import.py
```

## Java SDK

The Java SDK builds with Maven and targets Java 17 bytecode.

```bash
mvn -f sdk-java/pom.xml test
```

Current Java SDK surface:

- `TestDataFactory.local()`
- `.seed(...)`
- `.contract(Path)`
- `ContractDocument.id()`
- `ContractDocument.raw()`
- `ContractDocument.scenario(...)`
- `ScenarioRequest.scenarioId()`
- `ScenarioRequest.contract()`
- `ScenarioRequest.one()`
- `ScenarioRequest.count(n)`

## TypeScript SDK

Install dependencies and run tests:

```bash
cd sdk-typescript
npm ci
npm test
```

Current TypeScript SDK surface:

- `testDataFactory.local()`
- `.seed(...)`
- `.defaultSeed()`
- `.contract(path)`
- `ContractDocument.id()`
- `ContractDocument.defaultSeed()`
- `ContractDocument.raw()`
- `ContractDocument.scenario(...)`
- `ScenarioRequest.scenarioId()`
- `ScenarioRequest.contract()`
- `ScenarioRequest.one()`
- `ScenarioRequest.count(n)`

## API Server

Run the API locally:

```bash
python -m uvicorn testdata_factory_engine.server:app --reload
```

The static OpenAPI document is stored at `specs/openapi/testdata-factory.openapi.json`. Engine tests compare key parts of the static spec with the live FastAPI schema.

## Contract Schema

The packaged schema and published schema copy should stay in sync:

- `engine/src/testdata_factory_engine/schemas/tdf-contract.schema.json`
- `specs/contract-schema/tdf-contract.schema.json`

`engine/tests/test_packaging.py` checks that the packaged schema matches the spec copy.

## Documentation Checks

When changing documented command behavior, run the command examples that are affected. Useful smoke checks:

```bash
tdf --help
tdf validate examples/contracts/register.tdf.json
tdf validate --json examples/contracts/register.tdf.json
tdf generate --contract examples/contracts/register.tdf.json --scenario valid_signup --count 2 --seed docs
tdf scan --json-schema examples/schemas/customer.schema.json --out /tmp/customer.tdf.json
tdf scan --openapi examples/openapi/customer.openapi.json --operation createCustomer --out /tmp/create-customer.tdf.json
tdf models doctor
```

Framework examples under `examples/frameworks/` should stay source-tree friendly. Prefer concise snippets over adding framework-specific project scaffolding unless the example is meant to be run directly in this repository.

For form scanning:

```bash
tdf scan --url examples/forms/signup.html --id signup-form --out /tmp/signup-form.tdf.json
```

## Release Smoke Suite

Run the release smoke suite before release acceptance:

```bash
scripts/release-smoke.sh
```

The script installs the engine test extras in the active Python environment, installs Playwright Chromium, runs the `release_smoke` pytest subset, runs the Java SDK tests, and runs the TypeScript SDK tests.

To run only the pytest-marked release smoke coverage:

```bash
python -m pytest engine -m release_smoke
```

## Full Local Validation

Run the same suites covered by CI:

```bash
python -m pytest engine
mvn -f sdk-java/pom.xml test
(cd sdk-typescript && npm ci && npm test)
```

## Package Builds

Build local package artifacts:

```bash
python -m pip wheel ./engine --no-deps --wheel-dir /tmp/testdata-factory-dist
mvn -f sdk-java/pom.xml package
(cd sdk-typescript && npm run build && npm pack --pack-destination /tmp/testdata-factory-dist)
```
