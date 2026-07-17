# TestData Factory Requirements

Last updated: 2026-07-17

Project name: TestData Factory.

Repository name: `testdata-factory`.

## 1. Vision

TestData Factory is an open-source, local-first test data generator for automation engineers. It helps QA teams generate realistic, business-aware synthetic data for UI, API, and integration tests without depending on paid LLM APIs.

The system should infer not only the technical type of a field, such as string, number, date, or enum, but also its business meaning, such as phone number, email, password, national ID, amount, username, address, date of birth, or account number.

The generated output should be easy to use inside Java, TypeScript, and Python test code.

## 2. Core Principles

- Open source under MIT license.
- Local-first by default; no paid model dependency for the initial release.
- SDK-first developer experience, with API and CLI as supporting surfaces.
- One core engine and one contract format shared across all languages.
- Deterministic generation during test execution.
- LLMs assist with analysis and validation, but tests should not require live LLM calls by default.
- Contracts and generated scenarios must be reviewable and version-controlled.
- Field inference must be explainable enough for QA engineers to trust and correct it.
- The product should support single engineers and small QA teams, not only companies with large GPU infrastructure.

## 3. Target Users

- Automation engineers writing Selenium, Playwright, Cypress, JUnit, TestNG, or pytest tests.
- QA engineers who need realistic positive and negative test data.
- SDETs maintaining page objects and reusable test fixtures.
- Developers who need seed data for local testing.
- Open-source contributors extending business field types, model adapters, and framework integrations.

## 4. Non-Goals For V1

- No hosted SaaS product.
- No mandatory paid LLM integration.
- No production data anonymization or synthetic database cloning in V1.
- No attempt to fully understand arbitrary page object code without annotations or explicit metadata.
- No automatic test case authoring beyond data scenarios.
- No default reliance on large enterprise-only models requiring H100/H200-class hardware.
- No guarantee that URL scanning is perfect without human review.

## 5. Supported Inputs

### 5.1 URL/Form Scan

The CLI and API should scan a web page and detect form fields using a browser automation adapter.

Required capabilities:

- Load a URL with Playwright as the default scanning engine.
- Detect `input`, `textarea`, `select`, role-based controls, labels, placeholders, names, ids, aria attributes, validation attributes, and nearby text.
- Extract HTML validation hints such as `required`, `min`, `max`, `minlength`, `maxlength`, `pattern`, `type`, and select options.
- Detect simple field groups such as address blocks, payment-like blocks, signup forms, login forms, and profile forms.
- Produce a reviewable contract file.

Optional capabilities:

- Authenticated scans through saved browser state.
- Multi-step form scans.
- Screenshot-assisted scan when a local vision model is configured.

### 5.2 Explicit Contract

Users can define or edit a `.tdf.json` contract directly. This is the most reliable input and must be fully supported.

### 5.3 Page Object Metadata

Page object support should use explicit metadata instead of trying to infer every framework-specific class automatically.

Java example:

```java
@TdfPage("register")
class RegisterPage {
  @TdfField(selector = "#phone", businessType = "phone_number", country = "US", required = true)
  Locator phone;
}
```

TypeScript example:

```ts
export const registerFields = defineFields({
  phone: field("#phone").phone({ country: "US", required: true }),
});
```

Python example:

```py
register_fields = fields({
  "phone": field("#phone").phone(country="US", required=True),
})
```

### 5.4 API Schema Input

V1 should support OpenAPI and JSON Schema input when users already have structured API contracts.

Required:

- Import JSON Schema object properties.
- Import OpenAPI request schemas.
- Preserve enums, required fields, min/max constraints, formats, examples, and descriptions.

## 6. Contract Format

The contract is the central artifact shared by CLI, API, Java SDK, TypeScript SDK, and Python SDK.

File extension:

- `.tdf.json`

Required top-level fields:

- `schemaVersion`
- `id`
- `source`
- `locale`
- `fields`
- `scenarios`
- `generation`
- `validation`

Example:

```json
{
  "schemaVersion": "1.0",
  "id": "register",
  "source": {
    "type": "url",
    "value": "https://app.test/register"
  },
  "locale": {
    "country": "US",
    "language": "en"
  },
  "fields": {
    "phone": {
      "selector": "#phone",
      "dataType": "string",
      "businessType": "phone_number",
      "required": true,
      "constraints": {
        "country": "US",
        "minLength": 9,
        "maxLength": 14
      },
      "inference": {
        "confidence": 0.92,
        "signals": ["label: Phone", "input[type=tel]", "id: phone"]
      }
    }
  },
  "scenarios": [
    {
      "id": "valid_signup",
      "kind": "positive",
      "description": "All required signup fields contain valid values.",
      "fields": {
        "phone": { "strategy": "valid_phone" }
      }
    },
    {
      "id": "invalid_phone_letters",
      "kind": "negative",
      "description": "Phone field contains alphabetic characters.",
      "fields": {
        "phone": { "strategy": "invalid_alpha" }
      }
    }
  ],
  "generation": {
    "deterministic": true,
    "defaultSeed": "register-suite"
  },
  "validation": {
    "lastValidatedBy": "medium",
    "status": "needs_review"
  }
}
```

## 7. Business Field Types

V1 must include built-in support for common field meanings:

- `first_name`
- `last_name`
- `full_name`
- `username`
- `email`
- `password`
- `phone_number`
- `country_code`
- `address_line`
- `city`
- `state`
- `postal_code`
- `country`
- `date`
- `date_of_birth`
- `time`
- `datetime`
- `amount`
- `currency`
- `percentage`
- `quantity`
- `integer`
- `decimal`
- `boolean`
- `enum`
- `url`
- `domain`
- `uuid`
- `national_id`
- `passport_number`
- `tax_id`
- `account_number`
- `iban`
- `credit_card_number`
- `cvv`
- `expiry_date`
- `otp`
- `free_text`

Each business type must define:

- Positive generation strategies.
- Negative generation strategies.
- Boundary strategies when relevant.
- Locale/country sensitivity when relevant.
- Validation rules for generated values.

## 8. Scenario Types

V1 must generate the following scenario categories:

- Positive: valid complete data.
- Negative: invalid format.
- Negative: missing required field.
- Negative: invalid length.
- Negative: invalid range.
- Negative: invalid enum option.
- Boundary: min length.
- Boundary: max length.
- Boundary: min value.
- Boundary: max value.
- Boundary: date edge cases.
- Security-ish: common injection-like strings for text fields, opt-in only.
- Locale-specific: phone, ID, address, and postal formats when supported.

Generated scenarios should be structured, named, and stable.

## 9. Dual-Agent Workflow

The product concept includes two logical agents:

### 9.1 Analyzer/Generator Agent

Responsibilities:

- Infer field `dataType`.
- Infer field `businessType`.
- Propose constraints.
- Propose scenario definitions.
- Explain inference signals.
- Produce a contract draft.

### 9.2 Validator Agent

Responsibilities:

- Validate the contract draft.
- Detect inconsistent field types.
- Detect missing negative or boundary scenarios.
- Detect generated data that violates constraints.
- Return structured feedback and confidence scores.

Important implementation rule:

These agents are logical roles. They can run through one local model, multiple local models, or deterministic validators depending on configuration. V1 should not require two separate model downloads.

## 10. Local Model Strategy

V1 must support three local model profiles:

- `light`: low hardware requirements, lower accuracy.
- `balanced`: better accuracy, higher memory/CPU/GPU needs.
- `strong`: highest default local accuracy, requires a stronger consumer GPU or high unified memory machine.

The default inference provider should be local and configurable.

Recommended initial providers:

- Ollama provider.
- OpenAI-compatible local endpoint provider.
- llama.cpp/llama-server compatible provider.

The application must not bundle model weights. Users install models separately and remain responsible for upstream model licenses.

See [Local Model Profiles](model-profiles.md) for concrete model recommendations.

## 11. Runtime Generation Rule

During normal test execution, SDKs should not call an LLM by default.

Preferred flow:

1. User scans a URL, page metadata, or API schema.
2. TestData Factory produces a `.tdf.json` contract.
3. User reviews or edits the contract.
4. SDK generates data deterministically from the contract and seed during tests.
5. Optional: user re-runs analysis/validation when the page or schema changes.

Rationale:

- Faster tests.
- Lower hardware requirements in CI.
- No flaky LLM output during test execution.
- Reviewable data logic.
- Repeatable failed test reproduction.

## 12. Public Surfaces

### 12.1 CLI

Command target:

```bash
tdf scan --url https://app.test/register --out register.tdf.json
tdf scan --openapi openapi.yaml --operation createUser --out create-user.tdf.json
tdf validate register.tdf.json
tdf generate --contract register.tdf.json --scenario valid_signup --count 10
tdf serve --port 7331
tdf models doctor
```

Required commands:

- `scan`
- `validate`
- `generate`
- `serve`
- `models doctor`
- `init`

### 12.2 REST API

The REST API should be documented with OpenAPI.

Required endpoints:

- `POST /v1/contracts/analyze-url`
- `POST /v1/contracts/analyze-schema`
- `POST /v1/contracts/validate`
- `POST /v1/data/generate`
- `GET /v1/model-profiles`
- `GET /health`

### 12.3 Java SDK

Primary package target:

- Maven Central package: `io.github.iisleem.testdatafactory:testdata-factory`.

Required style:

```java
var factory = TestDataFactory.local()
    .seed("signup-suite")
    .contract("register.tdf.json");

var users = factory.scenario("valid_signup").count(5);
```

Required integrations:

- JUnit 5.
- TestNG.
- Selenium-friendly object output.
- Playwright Java-friendly object output.

Release requirement:

- Java SDK is part of the first complete release.

### 12.4 TypeScript SDK

Primary package target:

- npm package: `testdata-factory`.

Required style:

```ts
const factory = testDataFactory.local()
  .seed("signup-suite")
  .contract("register.tdf.json");

const users = factory.scenario("valid_signup").count(5);
```

Required integrations:

- Playwright.
- Cypress.
- Node test runners.

Release requirement:

- TypeScript SDK is part of the first complete release.

### 12.5 Python SDK

Primary package target:

- PyPI package: `testdata-factory-engine`.

Required style:

```py
factory = TestDataFactory.local().seed("signup-suite").contract("register.tdf.json")
users = factory.scenario("valid_signup").count(5)
```

Required integrations:

- pytest.
- Selenium Python.
- Playwright Python.

Release requirement:

- Python SDK is part of the first complete release.

## 13. Monorepo Structure

Target repository structure:

```text
testdata-factory/
  engine/
  cli/
  server/
  specs/
    openapi/
    contract-schema/
  sdk-java/
  sdk-typescript/
  sdk-python/
  adapters/
    java-junit5/
    java-testng/
    ts-playwright/
    ts-cypress/
    py-pytest/
  examples/
    java-junit5-selenium/
    java-testng-selenium/
    ts-playwright/
    ts-cypress/
    py-pytest-playwright/
  docs/
  docker/
```

## 14. Core Engine Ownership

There should be one source of truth for:

- Contract schema.
- Scenario definitions.
- Business type registry.
- Deterministic data generation.
- Validation rules.
- Model prompts.
- Analyzer output schema.

SDKs should be thin wrappers around the shared contract and generation rules.

Architecture decision:

- Python is selected for the first engine implementation because it is fast to build, has strong AI/local-model ecosystem support, and can expose CLI/server behavior quickly.

Selection criteria:

- Easy CLI/server packaging.
- Easy deterministic generation.
- Easy model provider integration.
- Easy cross-language SDK support.
- Low friction for contributors.

## 15. Data Output

Generated output must be a list of objects by default.

Example:

```json
[
  {
    "phone": "+962790000001",
    "email": "nora.saleh@example.test",
    "password": "Tda1!securePass"
  }
]
```

Output options:

- JSON array.
- JSON lines.
- Java object/map.
- TypeScript object.
- Python dict.
- CSV, optional.

Generated records should include optional metadata when requested:

```json
{
  "data": {
    "phone": "abc"
  },
  "meta": {
    "scenarioId": "invalid_phone_letters",
    "fieldStrategies": {
      "phone": "invalid_alpha"
    },
    "seed": "signup-suite:0"
  }
}
```

## 16. Validation Feedback

Validation output must be structured.

Example:

```json
{
  "status": "needs_review",
  "score": 0.82,
  "findings": [
    {
      "severity": "warning",
      "field": "phone",
      "message": "Phone field inferred from label and input type, but no country hint was found.",
      "recommendation": "Set constraints.country explicitly."
    }
  ]
}
```

Severity levels:

- `info`
- `warning`
- `error`

## 17. Determinism

Requirements:

- Same contract + same seed + same scenario + same version must produce the same generated data.
- Randomness must be seedable.
- LLM output must never be part of deterministic runtime generation unless the user explicitly opts in.
- SDKs must expose seed configuration.
- Generated output should include seed metadata when requested.

## 18. Configuration

Supported config file:

- `tdf.config.json`

Example:

```json
{
  "modelProfile": "balanced",
  "provider": {
    "type": "ollama",
    "baseUrl": "http://localhost:11434",
    "model": "qwen3:14b"
  },
  "locale": {
    "country": "US",
    "language": "en"
  },
  "generation": {
    "defaultSeed": "local",
    "includeMetadata": false
  }
}
```

Config priority:

1. SDK method arguments.
2. CLI flags.
3. Environment variables.
4. `tdf.config.json`.
5. Built-in defaults.

## 19. Security And Privacy

Requirements:

- Do not send scanned page content to external paid/cloud models by default.
- Do not log generated sensitive-looking values unless debug logging is explicitly enabled.
- Redact obvious secrets from scanned pages and configs.
- Generated emails should use safe test domains such as `example.test`.
- Generated phone numbers should be fake and documented as unsafe for calls/SMS.
- Payment-like data must be test-only.
- Local model endpoints should default to localhost.

## 20. Licensing

Project target license:

- MIT.

Model weights:

- Not bundled.
- User-installed.
- Governed by their own upstream licenses.

Dependencies:

- Prefer permissive licenses.
- Document any dependency with non-MIT license obligations.

## 21. Packaging

Required release artifacts:

- CLI binaries or installable packages.
- Docker image for server.
- Java SDK package.
- TypeScript SDK package.
- Python SDK package.
- OpenAPI spec.
- Contract JSON Schema.
- Example projects.
- Documentation site or GitHub docs.

## 22. Quality Bar

Required before first release:

- Unit tests for business type generators.
- Unit tests for validators.
- Contract schema tests.
- Snapshot tests for deterministic generation.
- Integration tests for URL scan on sample forms.
- SDK smoke tests in Java, TypeScript, and Python.
- Docker server smoke test.
- Documentation examples verified in CI.

## 23. V1 Feature Set

V1 is considered complete when it includes:

- Local model profiles: light, balanced, strong.
- Ollama provider.
- OpenAI-compatible local endpoint provider.
- URL form scanner.
- OpenAPI/JSON Schema import.
- `.tdf.json` contract format.
- Contract validator.
- Deterministic data generator.
- Positive, negative, and boundary scenario generation.
- CLI.
- REST API server.
- Java SDK.
- TypeScript SDK.
- Python SDK.
- JUnit 5 example.
- TestNG example.
- Playwright TypeScript example.
- Cypress example.
- pytest example.
- Docker self-hosting instructions.
- MIT license.

All three SDKs are required for the first complete public release. Internal implementation can still be sequenced by milestone, but the release should not ship as Java-only, TypeScript-only, or Python-only.

## 24. Roadmap

### V1

- English-first field inference.
- Locale-aware generation with configurable locale.
- US examples by default unless a contract specifies another country.
- Extensible locale system for phone, address, postal, identity, and payment-like fields.

### Post-V1

- Gradual multilingual field-label inference.
- Arabic field-label support.
- Additional locale packs contributed by maintainers and community.
- Benchmarks for each added language/locale.

## 25. Open Questions

These questions should be answered before implementation planning:

- Should the first URL scanner support only Playwright, or Playwright plus Selenium?
- Should payment and national ID generators be included in V1 or behind explicit opt-in?
- Should the REST API be generated from OpenAPI-first, or should the implementation generate the OpenAPI spec?
- What CI matrix should be required for Java, Node.js, and Python versions?
