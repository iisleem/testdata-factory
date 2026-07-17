# Troubleshooting

## `tdf` Command Not Found

Activate the virtual environment and install the engine from the repository root:

```bash
. .venv/bin/activate
python -m pip install -e 'engine[server]'
tdf --help
```

If the command is still unavailable, check that `.venv/bin` is on your `PATH` after activation.

## `ModuleNotFoundError: testdata_factory_engine`

Install the engine in the active environment:

```bash
python -m pip install -e 'engine[dev,server]'
```

When running Python snippets from another directory, use absolute paths for contracts or run from the repository root.

## Playwright Is Required For URL Scanning

`tdf scan --url` uses Playwright. Install the scanner extra:

```bash
python -m pip install -e 'engine[scanner]'
```

## Chromium Is Required For URL Scanning

Install the browser runtime:

```bash
python -m playwright install chromium
```

Then retry:

```bash
tdf scan --url examples/forms/signup.html --id signup-form --out /tmp/signup-form.tdf.json
```

## `No Supported Form Controls Were Found`

The scanner currently looks for supported form controls in rendered HTML. Check that the target page or file contains standard inputs, textareas, selects, labels, names, IDs, placeholders, ARIA attributes, or HTML validation attributes. For dynamic pages, make sure the controls exist when the page reaches `domcontentloaded`.

## Contract Validation Returns `invalid`

Use structured validation output:

```bash
tdf validate --json examples/contracts/invalid-missing-fields.tdf.json
```

Common causes:

- Missing required top-level properties such as `fields` or `scenarios`.
- Scenario fields that do not exist in `contract.fields`.
- Unsupported `dataType`, `businessType`, `source.type`, or scenario `kind`.
- Enum fields without values when generation needs `valid_enum`.

## Contract Validation Returns `needs_review`

`needs_review` means the contract can be structurally valid while still needing attention. A common example is a required field that is not covered by a positive scenario. Review the findings and update scenarios before relying on the contract in tests.

## `Unknown Scenario`

Generation requires a scenario ID that exists in the contract:

```bash
tdf generate --contract examples/contracts/register.tdf.json --scenario valid_signup
```

List scenario IDs by opening the contract and checking the `scenarios` array.

## API Returns `422`

`POST /v1/data/generate` returns structured validation feedback when the request or contract is invalid. Check:

- `contract` is a JSON object, not a path string.
- `scenarioId` matches a scenario in the contract.
- `count` is at least `1`.
- The embedded contract validates successfully.

## JSON Schema Import Fails

The JSON Schema importer expects an object schema with `properties`. If your schema uses only primitive, array, or deeply nested root types, create a wrapper object schema for the payload you want to generate.

## OpenAPI Import Fails

The OpenAPI importer reads JSON request body schemas. Check:

- The file is JSON.
- `--operation` matches an `operationId` or a `METHOD /path` selector.
- The selected operation has an `application/json` request body schema.

Examples:

```bash
tdf scan --openapi examples/openapi/customer.openapi.json --operation createCustomer --out /tmp/create.tdf.json
tdf import openapi examples/openapi/customer.openapi.json --operation 'PATCH /v1/customers/{customerId}' --out /tmp/update.tdf.json
```

## TypeScript SDK Cannot Find A Contract

The TypeScript SDK reads the path you pass to `.contract(...)` relative to the current working directory. From `sdk-typescript`, the bundled example contract is:

```ts
const contract = testDataFactory.local().contract("../examples/contracts/register.tdf.json");
```

Use an absolute path when running examples from another directory.

## Java SDK Cannot Find A Contract

The Java SDK reads the `Path` you pass to `.contract(...)`. From the repository root, use:

```java
Path.of("examples/contracts/register.tdf.json")
```

Use an absolute path when running from a build directory or IDE configuration with a different working directory.

## Model Provider Requests Are Not Implemented

`tdf models doctor` and `/v1/model-profiles` expose profile metadata. The current deterministic generation workflow does not call model providers. If you create `tdf.config.json`, treat provider settings as local configuration metadata for now.
