# User Manual

This manual covers installing TestData Factory from source, using the CLI, running the self-hosted API, using the SDKs, and working with contracts.

## Install From Source

Requirements:

- Python 3.11 or newer
- Git
- Optional for form scanning: Playwright Chromium
- Optional for Java SDK development: JDK 17 or newer and Maven
- Optional for TypeScript SDK development: Node.js 20 or newer

Install the Python engine:

```bash
git clone https://github.com/iisleem/testdata-factory.git
cd testdata-factory
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e 'engine[server]'
tdf --help
```

Install browser scanning support only when you need `tdf scan --url`:

```bash
python -m pip install -e 'engine[scanner]'
python -m playwright install chromium
```

For development and tests, install all local extras:

```bash
python -m pip install -e 'engine[dev,server,scanner]'
```

## Package Coordinates

The first stable release is version `1.0.0`.

- Python engine and CLI: `testdata-factory-engine`
- Java SDK: `io.github.iisleem.testdatafactory:testdata-factory`
- TypeScript SDK: `testdata-factory`

See [../CHANGELOG.md](../CHANGELOG.md) for release notes.

Build local package artifacts from the source tree:

```bash
python -m pip wheel ./engine --no-deps --wheel-dir /tmp/testdata-factory-dist
mvn -f sdk-java/pom.xml package
(cd sdk-typescript && npm run build && npm pack --pack-destination /tmp/testdata-factory-dist)
```

## Choosing An Integration Mode

Use the integration mode that matches where test data should be owned and reviewed:

- SDK direct usage: best when an automation test needs generated records inline and the test suite can read a committed `.tdf.json` contract. See the [pytest](../examples/frameworks/python-pytest/README.md), [JUnit 5](../examples/frameworks/java-junit/README.md), and [Playwright](../examples/frameworks/typescript-playwright/README.md) examples.
- CLI fixture generation: best when CI should generate deterministic JSON fixtures before a framework-specific test runner starts.
- Self-hosted API: best when several services, languages, or teams need one internal validation and generation endpoint.
- Scan/import plus review: best when creating or refreshing a contract from an HTML form, JSON Schema, or OpenAPI request body. Review and commit the generated contract before using it in tests.

## CLI

The `tdf` command is installed by the Python engine package.

### Initialize Local Config

```bash
tdf init --output tdf.config.json
```

The config records a local model profile and provider settings. Deterministic data generation from contracts does not require the provider to be running.

### Validate A Contract

```bash
tdf validate examples/contracts/register.tdf.json
tdf validate --json examples/contracts/register.tdf.json
```

Plain output is meant for humans. `--json` returns structured feedback with `status`, `score`, and `findings`.

Validation statuses:

- `valid`: schema and consistency checks passed.
- `needs_review`: contract is usable but has warnings, such as required fields not covered by a positive scenario.
- `invalid`: schema or scenario references must be fixed before generation.

### Generate Data

```bash
tdf generate \
  --contract examples/contracts/register.tdf.json \
  --scenario valid_signup \
  --count 2 \
  --seed docs
```

The command prints a JSON array. The same contract, scenario, count, and seed produce the same output.

Generate a negative case:

```bash
tdf generate \
  --contract examples/contracts/register.tdf.json \
  --scenario invalid_email_format \
  --count 1
```

### Scan HTML Forms

`tdf scan --url` accepts either a web URL or a local HTML file path. It uses Playwright and requires the scanner extra plus Chromium.

```bash
python -m pip install -e 'engine[scanner]'
python -m playwright install chromium
tdf scan --url examples/forms/signup.html --id signup-form --out /tmp/signup-form.tdf.json
tdf validate /tmp/signup-form.tdf.json
```

Review scanned contracts before committing them. The scanner uses form controls, labels, names, IDs, placeholders, ARIA attributes, validation attributes, and select options to infer fields.

### Import JSON Schema

```bash
tdf scan --json-schema examples/schemas/customer.schema.json --id customer-signup --out /tmp/customer.tdf.json
tdf import json-schema examples/schemas/customer.schema.json --id customer-signup --out /tmp/customer-imported.tdf.json
```

The importer expects an object schema with properties. It preserves supported constraints such as required fields, formats, min/max values, enum values, descriptions, examples, and defaults.

### Import OpenAPI

```bash
tdf scan \
  --openapi examples/openapi/customer.openapi.json \
  --operation createCustomer \
  --out /tmp/create-customer.tdf.json
```

`--operation` accepts either an `operationId` or a `METHOD /path` selector:

```bash
tdf import openapi \
  examples/openapi/customer.openapi.json \
  --operation 'PATCH /v1/customers/{customerId}' \
  --out /tmp/update-customer.tdf.json
```

The current importer reads JSON request body schemas.

### Import Page Objects

Page object import reads Java, TypeScript, and Python files without executing user code:

```bash
tdf scan --page-object examples/page-objects/typescript/register.page.ts --id register-page --out /tmp/register-page.tdf.json
tdf import page-object examples/page-objects/java/RegisterPage.java --id register-page --out /tmp/register-page-java.tdf.json
tdf import page-object examples/page-objects/python/register_page.py --id register-page --out /tmp/register-page-py.tdf.json
```

The importer detects common Selenium and Playwright locator fields, `@FindBy` annotations, `By.*` locators, `page.locator` / `getByLabel` / `getByPlaceholder` / `getByRole` style locators, and direct fill/select/check methods. It maps discovered controls through the normal analyzer so field names, labels, placeholders, locator attributes, and input types can infer business types such as email, phone, password, URL, amount, and date. Output contracts use `"source": {"type": "page_object", ...}` and should be reviewed before committing.

### Inspect Model Profiles

```bash
tdf models doctor
```

Model profiles are metadata for local analysis setup. Contract-based validation and data generation work without a model provider.

### Draft Scenario Additions With Local AI

AI assistance is opt-in and requires an explicit local provider config:

```bash
tdf ai scenarios \
  --contract examples/contracts/register.tdf.json \
  --config examples/ai/ollama.config.json \
  --profile light \
  --goal "Add security and boundary coverage"
```

The command runs a generator agent followed by a validator agent. The JSON output contains `proposal.scenarios` plus structured `validation` feedback. Review approved scenarios before copying them into `contract.scenarios`; deterministic `tdf generate` does not call the model.

## API Server

Install the server extra:

```bash
python -m pip install -e 'engine[server]'
```

Start the API locally:

```bash
python -m uvicorn testdata_factory_engine.server:app --host 127.0.0.1 --port 8000
```

Useful endpoints:

- `GET /health`
- `GET /v1/model-profiles`
- `POST /v1/contracts/validate`
- `POST /v1/data/generate`
- `POST /v1/ai/scenarios`

Create a generation request payload from the sample contract:

```bash
python - <<'PY'
import json
from pathlib import Path

payload = {
    "contract": json.loads(Path("examples/contracts/register.tdf.json").read_text()),
    "scenarioId": "valid_signup",
    "count": 2,
    "seed": "api-docs",
}
Path("/tmp/tdf-generate-request.json").write_text(json.dumps(payload), encoding="utf-8")
PY
```

Send the request:

```bash
curl -s \
  -X POST http://127.0.0.1:8000/v1/data/generate \
  -H 'content-type: application/json' \
  -d @/tmp/tdf-generate-request.json
```

Validate a contract through the API:

```bash
python - <<'PY'
import json
from pathlib import Path

payload = {
    "contract": json.loads(Path("examples/contracts/register.tdf.json").read_text())
}
Path("/tmp/tdf-validate-request.json").write_text(json.dumps(payload), encoding="utf-8")
PY

curl -s \
  -X POST http://127.0.0.1:8000/v1/contracts/validate \
  -H 'content-type: application/json' \
  -d @/tmp/tdf-validate-request.json
```

Draft scenario additions through the optional local AI endpoint:

```bash
python - <<'PY'
import json
from pathlib import Path

payload = {
    "contract": json.loads(Path("examples/contracts/register.tdf.json").read_text()),
    "provider": json.loads(Path("examples/ai/ollama.config.json").read_text())["provider"],
    "modelProfile": "light",
    "goal": "Add security and boundary coverage",
}
Path("/tmp/tdf-ai-scenarios-request.json").write_text(json.dumps(payload), encoding="utf-8")
PY

curl -s \
  -X POST http://127.0.0.1:8000/v1/ai/scenarios \
  -H 'content-type: application/json' \
  -d @/tmp/tdf-ai-scenarios-request.json
```

For self-hosting, run the API in your own environment and expose it through your normal ingress, authentication, TLS, logging, and rate-limit controls. The repository does not require a hosted TestData Factory service.

## SDKs

### Python

The Python SDK can generate records locally from contracts:

```python
from pathlib import Path
from testdata_factory_engine import TestDataFactory

factory = TestDataFactory.local().seed("python-sdk")
contract = factory.contract(Path("examples/contracts/register.tdf.json"))

record = contract.scenario("valid_signup").one()
records = contract.scenario("valid_signup").count(2)
```

Lower-level Python APIs are also available:

```python
from testdata_factory_engine import generate_records, load_contract, validate_contract_file

result = validate_contract_file("examples/contracts/register.tdf.json")
contract = load_contract("examples/contracts/register.tdf.json")
records = generate_records(contract, "valid_signup", count=2, seed="direct-api")
```

### TypeScript

The TypeScript SDK package is `testdata-factory`. It loads contracts and generates deterministic records locally with `.one()` and `.count(n)`.

```bash
cd sdk-typescript
npm ci
npm run build
```

Source-tree example after `npm run build`:

```ts
import { testDataFactory } from "./dist/src/index.js";

const users = testDataFactory
  .local()
  .seed("ts-sdk")
  .contract("../examples/contracts/register.tdf.json")
  .scenario("valid_signup")
  .count(2);

const invalidEmailUser = testDataFactory
  .local()
  .seed("ts-sdk")
  .contract("../examples/contracts/register.tdf.json")
  .scenario("invalid_email_format")
  .one();
```

Package consumers can import from `testdata-factory` instead of the local `./dist/src/index.js` path.

### Java

The Java SDK coordinate is `io.github.iisleem.testdatafactory:testdata-factory`. It loads contracts and generates deterministic records locally with `.one()` and `.count(n)`.

```bash
mvn -f sdk-java/pom.xml test
```

Example:

```java
import dev.testdatafactory.sdk.ContractDocument;
import dev.testdatafactory.sdk.TestDataFactory;

import java.nio.file.Path;
import java.util.List;
import java.util.Map;

ContractDocument contract = TestDataFactory
    .local()
    .seed("java-sdk")
    .contract(Path.of("examples/contracts/register.tdf.json"));

List<Map<String, Object>> users = contract
    .scenario("valid_signup")
    .count(2);

Map<String, Object> invalidEmailUser = contract
    .scenario("invalid_email_format")
    .one();
```

## Contract Basics

A contract is a `.tdf.json` file with:

- Top-level metadata: `schemaVersion`, `id`, `source`, and `locale`.
- A `fields` object describing technical type, business type, constraints, and inference signals.
- A `scenarios` array describing positive, negative, boundary, or security-oriented data cases.
- A `generation` object containing deterministic seed behavior.
- A `validation` object recording review state.

See [Contract Format](contract-format.md) for the schema, supported business types, and strategies.

## Examples

Bundled examples:

- `examples/contracts/register.tdf.json`: hand-authored registration contract.
- `examples/contracts/invalid-missing-fields.tdf.json`: invalid contract for validation feedback.
- `examples/forms/signup.html`: local form scan input.
- `examples/schemas/customer.schema.json`: JSON Schema import input.
- `examples/openapi/customer.openapi.json`: OpenAPI import input.
- `examples/page-objects/`: Java, TypeScript, and Python page object import inputs.
- `examples/frameworks/python-pytest/`: pytest direct SDK usage.
- `examples/frameworks/java-junit/`: JUnit 5 direct SDK usage snippet.
- `examples/frameworks/typescript-playwright/`: Playwright-style direct SDK usage snippet.

## Troubleshooting

See [Troubleshooting](troubleshooting.md) for common installation, scanner, contract, API, and SDK issues.
