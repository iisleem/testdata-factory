# Contract Format

TestData Factory contracts are JSON files with the `.tdf.json` extension. The contract schema is versioned independently from the engine source and is available at:

- `engine/src/testdata_factory_engine/schemas/tdf-contract.schema.json`
- `specs/contract-schema/tdf-contract.schema.json`

Validate a contract with:

```bash
tdf validate examples/contracts/register.tdf.json
tdf validate --json examples/contracts/register.tdf.json
```

## Top-Level Shape

Required top-level properties:

| Property | Purpose |
| --- | --- |
| `schemaVersion` | Contract schema version. The current value is `1.0`. |
| `id` | Stable contract identifier. Use letters, numbers, `_`, and `-`. |
| `source` | Where the contract came from: `url`, `openapi`, `json_schema`, `page_object`, or `manual`. |
| `locale` | Language and optional country used by the contract. |
| `fields` | Field definitions keyed by test-friendly field names. |
| `scenarios` | Positive, negative, boundary, or security scenario definitions. |
| `generation` | Deterministic generation settings. |
| `validation` | Current review status. |

Minimal example:

```json
{
  "schemaVersion": "1.0",
  "id": "register",
  "source": {
    "type": "manual",
    "value": "examples/register"
  },
  "locale": {
    "language": "en",
    "country": "US"
  },
  "fields": {
    "email": {
      "selector": "#email",
      "label": "Email",
      "dataType": "string",
      "businessType": "email",
      "required": true,
      "constraints": {
        "format": "email"
      },
      "inference": {
        "confidence": 1,
        "signals": ["manual"]
      }
    }
  },
  "scenarios": [
    {
      "id": "valid_signup",
      "kind": "positive",
      "description": "Required signup fields contain valid values.",
      "fields": {
        "email": {
          "strategy": "valid_email"
        }
      }
    }
  ],
  "generation": {
    "deterministic": true,
    "defaultSeed": "register-suite"
  },
  "validation": {
    "status": "valid"
  }
}
```

## Fields

Each field requires:

- `dataType`: one of `string`, `integer`, `decimal`, `boolean`, `date`, `datetime`, `time`, `enum`, `array`, or `object`.
- `businessType`: business meaning used to choose generation strategies.
- `required`: whether the field is required by the target form or schema.

Optional field metadata:

- `selector`: UI selector when the field comes from a page or form.
- `label`: human-readable label.
- `constraints`: validation hints such as `minLength`, `maxLength`, `minimum`, `maximum`, `pattern`, `format`, `country`, `values`, and `unique`.
- `dependencies`: optional cross-field hints for common form contracts.
- `inference`: confidence and signals explaining why a scanner or importer chose the field meaning.

Supported business types:

```text
first_name, last_name, full_name, username, email, password,
phone_number, country_code, address_line, city, state, postal_code,
country, date, date_of_birth, time, datetime, amount, currency,
percentage, quantity, integer, decimal, boolean, enum, url, domain,
uuid, national_id, passport_number, tax_id, account_number, iban,
credit_card_number, cvv, expiry_date, otp, free_text
```

### Cross-Field Dependencies

Field dependencies are additive in schema version `1.0`; existing contracts do not need them. They let generated records keep common field pairs valid by default and let scenarios intentionally break the pair.

Supported dependency properties:

| Property | Meaning |
| --- | --- |
| `matchesField` | This field should equal another field, such as `confirmPassword` matching `password`. |
| `rangeStartFor` | This date or datetime field is the start of a range. |
| `rangeEndFor` | This date or datetime field is the end of a range and should occur after its start field. |
| `minFor` | This numeric field is the minimum for a related maximum field. |
| `maxFor` | This numeric field is the maximum for a related minimum field. |

Example:

```json
{
  "confirmPassword": {
    "dataType": "string",
    "businessType": "password",
    "required": true,
    "dependencies": {
      "matchesField": "password"
    }
  }
}
```

## Scenarios

Scenario properties:

| Property | Purpose |
| --- | --- |
| `id` | Stable scenario identifier used by CLI, API, and SDK calls. |
| `kind` | `positive`, `negative`, `boundary`, or `security`. |
| `description` | Human-readable scenario summary. |
| `fields` | Per-field strategy or fixed value overrides. |

Scenario field overrides support:

- `strategy`: generation strategy name.
- `value`: fixed value. When present, this value is used directly.

Example:

```json
{
  "id": "invalid_email_format",
  "kind": "negative",
  "description": "Email field contains a value that is not a valid email address.",
  "fields": {
    "email": {
      "strategy": "invalid_email_format"
    }
  }
}
```

If a scenario references a field that is not defined in `fields`, validation returns an `invalid` result.

## Implemented Strategies

The current engine implements these strategy names:

```text
valid_first_name, valid_last_name, valid_full_name, valid_username,
valid_email, invalid_email_format, valid_phone, invalid_phone_format,
valid_country_code,
valid_address_line, valid_city, valid_state, valid_postal_code,
valid_country, invalid_alpha, valid_password, weak_password,
valid_integer, valid_decimal, valid_enum, valid_date, valid_time,
valid_datetime, valid_boolean, boolean_false, boolean_true,
valid_currency, valid_url, valid_domain,
valid_uuid, valid_national_id, valid_passport_number, valid_tax_id,
valid_account_number, valid_iban, valid_credit_card_number, valid_cvv,
valid_expiry_date, valid_otp, valid_free_text,
xss_payload, sql_injection_payload, null_value, empty_string,
whitespace_only, over_max_length, below_min_length, duplicate_value,
match_field, mismatch_field, range_end_after_start,
date_before_related_field, numeric_max_at_or_above_min,
numeric_max_below_min
```

When a scenario does not specify a strategy for a field, generation uses the default strategy for that field's `businessType`. A few field types, such as `enum`, require supporting constraints like `constraints.values`.

## Deterministic Generation

Generation uses a seed from one of these places:

1. The `--seed` CLI argument, API `seed`, or SDK `.seed(...)`.
2. The contract's `generation.defaultSeed`.

The same contract, scenario, count, and seed produce the same records. This makes contracts suitable for committed test fixtures and CI runs.

## Validation

Validation checks:

- Required top-level properties and JSON Schema rules.
- Unknown scenario field references.
- Positive scenario coverage for required fields.

When a contract has only warnings, such as missing positive coverage for a required field, validation returns `needs_review`. Invalid contracts cannot be loaded for generation.

## Importer Output

Form scans, JSON Schema imports, and OpenAPI imports generate contracts with `validation.status` set to `needs_review`. Review generated contracts before committing them because inference is intentionally transparent and editable.

Generated imports include a positive scenario and, where supported by the fields and constraints, additional negative, security, robustness, boundary, and cross-field scenarios for invalid email or phone values, weak passwords, missing required fields, XSS and SQL injection payloads, null/empty/whitespace values, length violations, duplicate unique fields, string length boundaries, numeric minimum and maximum values, enum values, boolean true/false values, date example boundaries, password confirmation mismatch, date range order, and numeric min/max pair order.

See `examples/contracts/advanced-register.tdf.json` for a compact manual contract using security, robustness, uniqueness, boolean, and cross-field scenarios.
