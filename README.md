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
python -m pip install -e 'engine[dev,server]'
python -m pytest engine
tdf --help
mvn -f sdk-java/pom.xml test
(cd sdk-typescript && npm ci && npm test)
```

Install browser scanning support when working on form scanning:

```bash
python -m pip install -e 'engine[scanner]'
python -m playwright install chromium
tdf scan --url path/to/form.html --id sample-form --out sample-form.tdf.json
tdf scan --json-schema customer.schema.json --out customer.tdf.json
tdf scan --openapi openapi.json --operation createCustomer --out create-customer.tdf.json
```

Run the local API server:

```bash
uvicorn testdata_factory_engine.server:app --reload
```
