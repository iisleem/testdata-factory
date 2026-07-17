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
