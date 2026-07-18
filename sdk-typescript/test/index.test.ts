import { strict as assert } from "node:assert";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { ContractDocument, testDataFactory, type ContractJson } from "../src/index.js";

const contractPath = "../examples/contracts/register.tdf.json";
const schemaPath = "../specs/contract-schema/tdf-contract.schema.json";

test("loads contract fixture", () => {
  const contract = testDataFactory.local().seed("ts-sdk").contract(contractPath);

  assert.equal(contract.id(), "register");
  assert.equal(testDataFactory.local().seed("ts-sdk").defaultSeed(), "ts-sdk");
});

test("creates scenario request", () => {
  const contract = testDataFactory.local().contract(contractPath);
  const scenario = contract.scenario("valid_signup");

  assert.equal(scenario.scenarioId(), "valid_signup");
  assert.equal(scenario.contract().id(), "register");
});

test("release smoke generates deterministic records", () => {
  const client = testDataFactory.local().seed("release-ts-sdk");

  const first = client.contract(contractPath).scenario("valid_signup").count(2);
  const second = client.contract(contractPath).scenario("valid_signup").count(2);
  const invalidEmailUser = client.contract(contractPath).scenario("invalid_email_format").one();

  assert.deepEqual(first, second);
  assert.equal(first.length, 2);
  assert.match(String(first[0].email), /@example\.test$/);
  assert.equal(invalidEmailUser.email, "not-an-email");
});

test("generates scenario records", () => {
  const users = testDataFactory
    .local()
    .seed("ts-sdk")
    .contract(contractPath)
    .scenario("valid_signup")
    .count(2);

  assert.equal(users.length, 2);
  assert.deepEqual(Object.keys(users[0]), [
    "firstName",
    "email",
    "phone",
    "password",
    "age",
    "plan",
    "birthDate",
    "newsletter",
  ]);
  assert.match(String(users[0].email), /@example\.test$/);
  assert.match(String(users[0].phone), /^\+155501/);
  assert.equal(typeof users[0].age, "number");
  assert.ok(Number(users[0].age) >= 18);
  assert.ok(Number(users[0].age) <= 99);
  assert.ok(["basic", "pro", "enterprise"].includes(String(users[0].plan)));
  assert.equal(typeof users[0].newsletter, "boolean");
});

test("generation is repeatable for the same seed", () => {
  const first = testDataFactory.local().seed("ts-sdk").contract(contractPath).scenario("valid_signup").count(2);
  const second = testDataFactory.local().seed("ts-sdk").contract(contractPath).scenario("valid_signup").count(2);
  const differentSeed = testDataFactory
    .local()
    .seed("ts-sdk-other")
    .contract(contractPath)
    .scenario("valid_signup")
    .count(2);

  assert.deepEqual(first, second);
  assert.notDeepEqual(first, differentSeed);
});

test("applies negative scenario strategies", () => {
  const user = testDataFactory
    .local()
    .seed("ts-sdk")
    .contract(contractPath)
    .scenario("invalid_email_format")
    .one();

  assert.equal(user.email, "not-an-email");
  assert.match(String(user.password), /^Tdf!/);
});

test("applies generated import negative scenario strategies", () => {
  const contract = new ContractDocument(generatedImportNegativeContract(), "ts-sdk");

  const invalidPhoneUser = contract.scenario("invalid_phone_format").one();
  const weakPasswordUser = contract.scenario("weak_password").one();

  assert.equal(invalidPhoneUser.phone, "not-a-phone");
  assert.match(String(invalidPhoneUser.password), /^Tdf!/);
  assert.equal(weakPasswordUser.password, "password");
  assert.match(String(weakPasswordUser.phone), /^\+155501/);
});

test("applies security robustness boundary and duplicate strategies", () => {
  const contract = new ContractDocument(advancedGenerationContract(), "ts-sdk-advanced");

  assert.equal(contract.scenario("xss_payloads").one().notes, "<script>alert('tdf')</script>");
  assert.equal(contract.scenario("sql_injection_payloads").one().notes, "admin' OR '1'='1");

  const nullRecord = contract.scenario("null_required_fields").one();
  assert.ok(Object.hasOwn(nullRecord, "email"));
  assert.equal(nullRecord.email, null);

  assert.equal(contract.scenario("empty_string_fields").one().notes, "");
  assert.equal(contract.scenario("empty_dependent_date_field").one().endDate, "");
  assert.equal(contract.scenario("whitespace_only_fields").one().notes, "   ");
  assert.equal(String(contract.scenario("below_min_length_fields").one().notes).length, 2);
  assert.equal(String(contract.scenario("over_max_length_fields").one().notes).length, 11);
  assert.equal(contract.scenario("boolean_false_boundaries").one().marketingOptIn, false);
  assert.equal(contract.scenario("boolean_true_boundaries").one().marketingOptIn, true);

  const duplicateRecords = contract.scenario("duplicate_unique_fields").count(2);
  assert.equal(duplicateRecords[0].email, "duplicate@example.test");
  assert.equal(duplicateRecords[0].email, duplicateRecords[1].email);
});

test("applies cross-field dependencies for valid and invalid records", () => {
  const contract = new ContractDocument(advancedGenerationContract(), "ts-sdk-advanced");

  const happyRecord = contract.scenario("valid_advanced").one();
  const explicitValidRecord = contract.scenario("explicit_valid_relationships").one();
  const rangeEndStrategyRecord = contract.scenario("range_end_after_start_relationship").one();
  const normalOverrideRecord = contract.scenario("normal_strategy_confirmation_matches").one();
  const mismatchRecord = contract.scenario("mismatched_confirmation_fields").one();
  const invalidDateRecord = contract.scenario("invalid_date_ranges").one();
  const invalidNumericRecord = contract.scenario("invalid_numeric_ranges").one();

  assert.equal(happyRecord.confirmPassword, happyRecord.password);
  assert.ok(String(happyRecord.endDate) > String(happyRecord.startDate));
  assert.ok(Number(happyRecord.maxGuests) >= Number(happyRecord.minGuests));

  assert.equal(explicitValidRecord.confirmPassword, explicitValidRecord.password);
  assert.ok(String(explicitValidRecord.endDate) > String(explicitValidRecord.startDate));
  assert.ok(Number(explicitValidRecord.maxGuests) >= Number(explicitValidRecord.minGuests));

  assert.ok(String(rangeEndStrategyRecord.endDate) > String(rangeEndStrategyRecord.startDate));
  assert.equal(normalOverrideRecord.confirmPassword, normalOverrideRecord.password);
  assert.notEqual(normalOverrideRecord.confirmPassword, "password");
  assert.notEqual(mismatchRecord.confirmPassword, mismatchRecord.password);
  assert.ok(String(invalidDateRecord.endDate) < String(invalidDateRecord.startDate));
  assert.ok(Number(invalidNumericRecord.maxGuests) < Number(invalidNumericRecord.minGuests));
});

test("unknown scenario fails clearly", () => {
  const scenario = testDataFactory.local().contract(contractPath).scenario("missing_scenario");

  assert.throws(() => scenario.one(), /Unknown scenario: missing_scenario/);
});

test("default generation covers all schema business types", () => {
  const businessTypes = schemaBusinessTypes();
  const contract = new ContractDocument(businessTypeContract(businessTypes), "ts-sdk");

  const first = contract.scenario("default_business_types").count(2);
  const second = contract.scenario("default_business_types").count(2);

  assert.deepEqual(first, second);
  assert.deepEqual(new Set(Object.keys(first[0])), new Set(businessTypes));
  assertBusinessTypeRecord(first[0]);
});

function schemaBusinessTypes(): string[] {
  const schema = JSON.parse(readFileSync(schemaPath, "utf8")) as {
    $defs: {
      field: {
        properties: {
          businessType: {
            enum: string[];
          };
        };
      };
    };
  };
  return schema.$defs.field.properties.businessType.enum;
}

function businessTypeContract(businessTypes: string[]): ContractJson {
  return {
    schemaVersion: "1.0",
    id: "business-type-defaults",
    source: {
      type: "manual",
      value: "business-type-defaults",
    },
    locale: {
      language: "en",
      country: "US",
    },
    fields: Object.fromEntries(businessTypes.map((businessType) => [businessType, businessTypeField(businessType)])),
    scenarios: [
      {
        id: "default_business_types",
        kind: "positive",
        description: "Generate one value for every supported business type.",
        fields: {},
      },
    ],
    generation: {
      deterministic: true,
      defaultSeed: "business-type-suite",
    },
    validation: {
      status: "valid",
    },
  };
}

function generatedImportNegativeContract(): ContractJson {
  return {
    schemaVersion: "1.0",
    id: "generated-import-negatives",
    source: {
      type: "manual",
      value: "generated-import-negatives",
    },
    locale: {
      language: "en",
      country: "US",
    },
    fields: {
      phone: {
        dataType: "string",
        businessType: "phone_number",
        required: true,
      },
      password: {
        dataType: "string",
        businessType: "password",
        required: true,
      },
    },
    scenarios: [
      {
        id: "invalid_phone_format",
        kind: "negative",
        description: "Phone field contains an invalid number.",
        fields: {
          phone: {
            strategy: "invalid_phone_format",
          },
        },
      },
      {
        id: "weak_password",
        kind: "negative",
        description: "Password field contains an obviously weak value.",
        fields: {
          password: {
            strategy: "weak_password",
          },
        },
      },
    ],
    generation: {
      deterministic: true,
      defaultSeed: "generated-import-suite",
    },
    validation: {
      status: "valid",
    },
  };
}

function advancedGenerationContract(): ContractJson {
  return {
    schemaVersion: "1.0",
    id: "advanced-generation",
    source: {
      type: "manual",
      value: "advanced-generation",
    },
    locale: {
      language: "en",
      country: "US",
    },
    fields: {
      email: {
        dataType: "string",
        businessType: "email",
        required: true,
        constraints: {
          format: "email",
          unique: true,
        },
      },
      password: {
        dataType: "string",
        businessType: "password",
        required: true,
        constraints: {
          minLength: 12,
          maxLength: 72,
        },
      },
      confirmPassword: {
        dataType: "string",
        businessType: "password",
        required: true,
        constraints: {
          minLength: 12,
          maxLength: 72,
        },
        dependencies: {
          matchesField: "password",
        },
      },
      startDate: {
        dataType: "date",
        businessType: "date",
        required: true,
        dependencies: {
          rangeStartFor: "endDate",
        },
      },
      endDate: {
        dataType: "date",
        businessType: "date",
        required: true,
        dependencies: {
          rangeEndFor: "startDate",
        },
      },
      minGuests: {
        dataType: "integer",
        businessType: "integer",
        required: true,
        constraints: {
          minimum: 1,
          maximum: 5,
        },
        dependencies: {
          minFor: "maxGuests",
        },
      },
      maxGuests: {
        dataType: "integer",
        businessType: "integer",
        required: true,
        constraints: {
          minimum: 1,
          maximum: 10,
        },
        dependencies: {
          maxFor: "minGuests",
        },
      },
      notes: {
        dataType: "string",
        businessType: "free_text",
        required: false,
        constraints: {
          minLength: 3,
          maxLength: 10,
        },
      },
      marketingOptIn: {
        dataType: "boolean",
        businessType: "boolean",
        required: false,
      },
    },
    scenarios: [
      {
        id: "valid_advanced",
        kind: "positive",
        description: "Valid advanced fields.",
        fields: {},
      },
      {
        id: "explicit_valid_relationships",
        kind: "positive",
        description: "Explicit relational strategies.",
        fields: {
          confirmPassword: {
            strategy: "match_field",
          },
          endDate: {
            strategy: "date_after_related_field",
          },
          maxGuests: {
            strategy: "numeric_max_at_or_above_min",
          },
        },
      },
      {
        id: "range_end_after_start_relationship",
        kind: "positive",
        description: "Range end strategy keeps end date after start date.",
        fields: {
          endDate: {
            strategy: "range_end_after_start",
          },
        },
      },
      {
        id: "normal_strategy_confirmation_matches",
        kind: "positive",
        description: "Generated dependent fields honor dependencies after normal strategy generation.",
        fields: {
          confirmPassword: {
            strategy: "weak_password",
          },
        },
      },
      {
        id: "xss_payloads",
        kind: "security",
        description: "XSS probe.",
        fields: {
          notes: {
            strategy: "xss_payload",
          },
        },
      },
      {
        id: "sql_injection_payloads",
        kind: "security",
        description: "SQL injection probe.",
        fields: {
          notes: {
            strategy: "sql_injection_payload",
          },
        },
      },
      {
        id: "null_required_fields",
        kind: "negative",
        description: "Null required field.",
        fields: {
          email: {
            strategy: "null_value",
          },
        },
      },
      {
        id: "empty_string_fields",
        kind: "negative",
        description: "Empty string field.",
        fields: {
          notes: {
            strategy: "empty_string",
          },
        },
      },
      {
        id: "empty_dependent_date_field",
        kind: "negative",
        description: "Empty string on a dependent date field.",
        fields: {
          endDate: {
            strategy: "empty_string",
          },
        },
      },
      {
        id: "whitespace_only_fields",
        kind: "negative",
        description: "Whitespace-only field.",
        fields: {
          notes: {
            strategy: "whitespace_only",
          },
        },
      },
      {
        id: "below_min_length_fields",
        kind: "negative",
        description: "Below minimum length.",
        fields: {
          notes: {
            strategy: "below_min_length",
          },
        },
      },
      {
        id: "over_max_length_fields",
        kind: "negative",
        description: "Over maximum length.",
        fields: {
          notes: {
            strategy: "over_max_length",
          },
        },
      },
      {
        id: "duplicate_unique_fields",
        kind: "negative",
        description: "Duplicate unique field.",
        fields: {
          email: {
            strategy: "duplicate_value",
          },
        },
      },
      {
        id: "boolean_false_boundaries",
        kind: "boundary",
        description: "False boolean.",
        fields: {
          marketingOptIn: {
            strategy: "boolean_false",
          },
        },
      },
      {
        id: "boolean_true_boundaries",
        kind: "boundary",
        description: "True boolean.",
        fields: {
          marketingOptIn: {
            strategy: "boolean_true",
          },
        },
      },
      {
        id: "mismatched_confirmation_fields",
        kind: "negative",
        description: "Password confirmation mismatch.",
        fields: {
          confirmPassword: {
            strategy: "mismatch_field",
          },
        },
      },
      {
        id: "invalid_date_ranges",
        kind: "negative",
        description: "Date range is reversed.",
        fields: {
          endDate: {
            strategy: "date_before_related_field",
          },
        },
      },
      {
        id: "invalid_numeric_ranges",
        kind: "negative",
        description: "Maximum is below minimum.",
        fields: {
          maxGuests: {
            strategy: "numeric_max_below_min",
          },
        },
      },
    ],
    generation: {
      deterministic: true,
      defaultSeed: "advanced-generation-suite",
    },
    validation: {
      status: "valid",
    },
  };
}

function businessTypeField(businessType: string): ContractJson["fields"][string] {
  const field: ContractJson["fields"][string] = {
    dataType: dataTypeFor(businessType),
    businessType,
    required: false,
  };
  if (businessType === "enum") {
    field.constraints = { values: ["basic", "pro", "enterprise"] };
  } else if (["integer", "quantity"].includes(businessType)) {
    field.constraints = { minimum: 10, maximum: 20 };
  } else if (["decimal", "amount", "percentage"].includes(businessType)) {
    field.constraints = { minimum: 1, maximum: 9 };
  } else if (businessType === "phone_number") {
    field.constraints = { country: "US" };
  }
  return field;
}

function dataTypeFor(businessType: string): string {
  if (["integer", "quantity"].includes(businessType)) {
    return "integer";
  }
  if (["decimal", "amount", "percentage"].includes(businessType)) {
    return "decimal";
  }
  if (["boolean", "enum", "time", "datetime"].includes(businessType)) {
    return businessType;
  }
  if (["date", "date_of_birth"].includes(businessType)) {
    return "date";
  }
  return "string";
}

function assertBusinessTypeRecord(record: Record<string, unknown>): void {
  assert.match(String(record.email), /@example\.test$/);
  assert.match(String(record.phone_number), /^\+155501\d{4}$/);
  assert.match(String(record.country_code), /^[A-Z]{2}$/);
  assert.match(String(record.address_line), /^\d{3} [A-Za-z ]+$/);
  assert.match(String(record.postal_code), /^\d{5}$/);
  assert.match(String(record.currency), /^[A-Z]{3}$/);
  assert.match(String(record.url), /^https:\/\/app-\d{3}\.example\.test\/resource-1$/);
  assert.match(String(record.domain), /^service-\d{3}\.example\.test$/);
  assert.match(String(record.uuid), /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  assert.match(String(record.national_id), /^NID-\d{9}$/);
  assert.match(String(record.passport_number), /^[PTX]\d{8}$/);
  assert.match(String(record.tax_id), /^TAX-\d{8}$/);
  assert.match(String(record.account_number), /^000\d{9}$/);
  assert.ok(ibanIsValid(String(record.iban)));
  assert.match(String(record.credit_card_number), /^411111\d{10}$/);
  assert.ok(luhnIsValid(String(record.credit_card_number)));
  assert.match(String(record.cvv), /^\d{3}$/);
  assert.match(String(record.expiry_date), /^\d{2}\/3\d$/);
  assert.match(String(record.otp), /^\d{6}$/);
  assert.ok(!Number.isNaN(Date.parse(String(record.datetime))));
  assert.match(String(record.time), /^\d{2}:\d{2}:00$/);
}

function ibanIsValid(value: string): boolean {
  return /^GB\d{2}TEST\d{14}$/.test(value) && ibanMod97(`${value.slice(4)}${value.slice(0, 4)}`) === 1;
}

function ibanMod97(value: string): number {
  let remainder = 0;
  for (const character of value.toUpperCase()) {
    let digits: string;
    if (/[0-9]/.test(character)) {
      digits = character;
    } else if (/[A-Z]/.test(character)) {
      digits = String(character.charCodeAt(0) - 55);
    } else {
      return -1;
    }
    for (const digit of digits) {
      remainder = (remainder * 10 + Number(digit)) % 97;
    }
  }
  return remainder;
}

function luhnIsValid(value: string): boolean {
  let total = 0;
  const reversed = [...value].reverse();
  for (let index = 0; index < reversed.length; index += 1) {
    let digit = Number(reversed[index]);
    if (index % 2 === 1) {
      digit *= 2;
      if (digit > 9) {
        digit -= 9;
      }
    }
    total += digit;
  }
  return total % 10 === 0;
}
