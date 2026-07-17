# TestData Factory

TestData Factory is an open-source, local-first toolkit for creating deterministic synthetic data for automated tests. It turns reviewed `.tdf.json` contracts, scanned forms, JSON Schema files, or OpenAPI request schemas into repeatable scenario-driven test records.

The core workflow is designed for automation engineers:

- Draft or import a contract for the form, endpoint, or payload under test.
- Review the inferred fields, constraints, and scenarios.
- Generate stable data in CI, local test runs, SDKs, or a self-hosted API without requiring a paid cloud model.

The initial release wave is version `0.1.0`.

## What Works Today

- Validate TestData Factory contracts with structured feedback.
- Generate deterministic JSON records from contract scenarios and seeds.
- Draft contracts from local or remote HTML forms with Playwright.
- Import JSON Schema object properties and OpenAPI JSON request bodies.
- Run a self-hosted FastAPI server for validation and generation.
- Generate locally from Python, Java, and TypeScript SDKs with `.one()` and `.count(n)`.
- Inspect local model profile metadata for light, balanced, and strong local setups.

TestData Factory does not require a hosted service by default. The implemented generation path is contract-based and deterministic, so normal test execution can run fully locally.

## Package Coordinates

- Python engine and CLI: `testdata-factory-engine`
- Java SDK: `io.github.iisleem.testdatafactory:testdata-factory`
- TypeScript SDK: `testdata-factory`

See [CHANGELOG.md](CHANGELOG.md) for release notes.

## Quick Start

Requirements:

- Python 3.11 or newer
- Git

Install the engine from source:

```bash
git clone https://github.com/iisleem/testdata-factory.git
cd testdata-factory
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e 'engine[server]'
```

Validate the bundled sample contract:

```bash
tdf validate examples/contracts/register.tdf.json
```

Generate two deterministic records:

```bash
tdf generate \
  --contract examples/contracts/register.tdf.json \
  --scenario valid_signup \
  --count 2 \
  --seed quickstart
```

Start the local API server:

```bash
python -m uvicorn testdata_factory_engine.server:app --reload
```

Then check it from another terminal:

```bash
curl http://127.0.0.1:8000/health
```

## Supported Workflows

### Contract-First Generation

Keep `.tdf.json` contracts beside the tests that consume them. Contracts define fields, business meanings, scenarios, and deterministic seed behavior.

```bash
tdf validate examples/contracts/register.tdf.json --json
tdf generate --contract examples/contracts/register.tdf.json --scenario invalid_email_format
```

See [Contract Format](docs/contract-format.md) for the schema and supported business types.

### Form Scanning

Install the scanner extra and Chromium before scanning HTML forms:

```bash
python -m pip install -e 'engine[scanner]'
python -m playwright install chromium
tdf scan --url examples/forms/signup.html --id signup-form --out /tmp/signup-form.tdf.json
```

`--url` accepts a web URL or a local HTML file path. Generated contracts should be reviewed before committing.

### JSON Schema and OpenAPI Import

Use `tdf scan` when you want one command for every source type:

```bash
tdf scan --json-schema examples/schemas/customer.schema.json --out /tmp/customer.tdf.json
tdf scan --openapi examples/openapi/customer.openapi.json --operation createCustomer --out /tmp/create-customer.tdf.json
```

Use `tdf import` when you want to call the schema importers directly:

```bash
tdf import json-schema examples/schemas/customer.schema.json --out /tmp/customer.tdf.json
tdf import openapi examples/openapi/customer.openapi.json --operation 'PATCH /v1/customers/{customerId}' --out /tmp/update-customer.tdf.json
```

### Self-Hosted API

The API exposes health, model profile, validation, and generation endpoints:

- `GET /health`
- `GET /v1/model-profiles`
- `POST /v1/contracts/validate`
- `POST /v1/data/generate`

Run it locally with:

```bash
python -m uvicorn testdata_factory_engine.server:app --host 127.0.0.1 --port 8000
```

For team use, host the API inside your own network and put authentication, TLS, logging, and rate limits in front of it using your normal platform controls. There is no hosted TestData Factory cloud dependency in the default workflow.

## CLI Overview

```bash
tdf init --output tdf.config.json
tdf validate examples/contracts/register.tdf.json
tdf validate --json examples/contracts/register.tdf.json
tdf generate --contract examples/contracts/register.tdf.json --scenario valid_signup --count 3
tdf scan --url examples/forms/signup.html --id signup-form --out /tmp/signup-form.tdf.json
tdf scan --json-schema examples/schemas/customer.schema.json --out /tmp/customer.tdf.json
tdf scan --openapi examples/openapi/customer.openapi.json --operation createCustomer --out /tmp/create-customer.tdf.json
tdf models doctor
```

See the [User Manual](docs/user-manual.md) for command details and examples.

## SDK Overview

All three SDKs can load a contract, select a scenario, and generate deterministic records locally.

Python:

```python
from pathlib import Path
from testdata_factory_engine import TestDataFactory

users = (
    TestDataFactory.local()
    .seed("pytest-suite")
    .contract(Path("examples/contracts/register.tdf.json"))
    .scenario("valid_signup")
    .count(2)
)

invalid_email_user = (
    TestDataFactory.local()
    .seed("pytest-suite")
    .contract(Path("examples/contracts/register.tdf.json"))
    .scenario("invalid_email_format")
    .one()
)
```

Java:

```java
import dev.testdatafactory.sdk.TestDataFactory;

import java.nio.file.Path;
import java.util.List;
import java.util.Map;

List<Map<String, Object>> users = TestDataFactory.local()
    .seed("junit-suite")
    .contract(Path.of("examples/contracts/register.tdf.json"))
    .scenario("valid_signup")
    .count(2);

Map<String, Object> invalidEmailUser = TestDataFactory.local()
    .seed("junit-suite")
    .contract(Path.of("examples/contracts/register.tdf.json"))
    .scenario("invalid_email_format")
    .one();
```

TypeScript:

```ts
import { testDataFactory } from "testdata-factory";

const users = testDataFactory
  .local()
  .seed("playwright-suite")
  .contract("examples/contracts/register.tdf.json")
  .scenario("valid_signup")
  .count(2);

const invalidEmailUser = testDataFactory
  .local()
  .seed("playwright-suite")
  .contract("examples/contracts/register.tdf.json")
  .scenario("invalid_email_format")
  .one();
```

See [User Manual](docs/user-manual.md#sdks) for SDK setup and source-tree examples.

## Documentation

- [User Manual](docs/user-manual.md)
- [Contract Format](docs/contract-format.md)
- [Model Profiles](docs/model-profiles.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Developer Guide](docs/developer-guide.md)
- [Changelog](CHANGELOG.md)

## Development

Install development dependencies:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e 'engine[dev,server,scanner]'
```

Run the local validation suite:

```bash
python -m pytest engine
mvn -f sdk-java/pom.xml test
(cd sdk-typescript && npm ci && npm test)
```

Build local package artifacts:

```bash
python -m pip wheel ./engine --no-deps --wheel-dir /tmp/testdata-factory-dist
mvn -f sdk-java/pom.xml package
(cd sdk-typescript && npm run build && npm pack --pack-destination /tmp/testdata-factory-dist)
```

Run the release smoke suite before release acceptance:

```bash
python3 -m venv .venv
. .venv/bin/activate
scripts/release-smoke.sh
```

The smoke command installs the engine test extras in the active Python environment, runs CLI import/scan/validate/generate checks, exercises API validation and generation responses, and runs the Java and TypeScript SDK tests.

## License

TestData Factory is released under the [MIT License](LICENSE).
