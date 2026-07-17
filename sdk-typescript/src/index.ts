import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";

export type ContractJson = {
  id: string;
  fields: Record<string, ContractField>;
  scenarios: ScenarioDefinition[];
  generation: {
    defaultSeed: string;
    [key: string]: unknown;
  };
  [key: string]: unknown;
};

export type ContractField = {
  businessType: string;
  constraints?: Record<string, unknown>;
  [key: string]: unknown;
};

export type ScenarioDefinition = {
  id: string;
  fields: Record<string, ScenarioFieldOverride>;
  [key: string]: unknown;
};

export type ScenarioFieldOverride = {
  strategy?: string;
  value?: unknown;
  [key: string]: unknown;
};

export type GeneratedRecord = Record<string, unknown>;

export class ContractDocument {
  constructor(
    private readonly contractJson: ContractJson,
    private readonly defaultSeedValue?: string,
  ) {}

  id(): string {
    return this.contractJson.id;
  }

  defaultSeed(): string | undefined {
    return this.defaultSeedValue;
  }

  raw(): ContractJson {
    return this.contractJson;
  }

  scenario(scenarioId: string): ScenarioRequest {
    return new ScenarioRequest(this, scenarioId);
  }
}

export class ScenarioRequest {
  constructor(
    private readonly contractDocument: ContractDocument,
    private readonly idValue: string,
  ) {}

  contract(): ContractDocument {
    return this.contractDocument;
  }

  scenarioId(): string {
    return this.idValue;
  }

  one(): GeneratedRecord {
    return this.count(1)[0];
  }

  count(count: number): GeneratedRecord[] {
    return generateRecords(
      this.contractDocument.raw(),
      this.idValue,
      count,
      this.contractDocument.defaultSeed(),
    );
  }
}

export class TestDataFactoryClient {
  constructor(private readonly defaultSeedValue?: string) {}

  seed(seed: string): TestDataFactoryClient {
    return new TestDataFactoryClient(seed);
  }

  defaultSeed(): string | undefined {
    return this.defaultSeedValue;
  }

  contract(path: string): ContractDocument {
    const data = JSON.parse(readFileSync(path, "utf8")) as ContractJson;
    return new ContractDocument(data, this.defaultSeedValue);
  }
}

export const testDataFactory = {
  local(): TestDataFactoryClient {
    return new TestDataFactoryClient();
  },
};

const defaultStrategies: Record<string, string> = {
  first_name: "valid_first_name",
  last_name: "valid_last_name",
  full_name: "valid_full_name",
  username: "valid_username",
  email: "valid_email",
  password: "valid_password",
  phone_number: "valid_phone",
  integer: "valid_integer",
  quantity: "valid_integer",
  decimal: "valid_decimal",
  amount: "valid_decimal",
  percentage: "valid_decimal",
  enum: "valid_enum",
  date: "valid_date",
  date_of_birth: "valid_date",
  boolean: "valid_boolean",
  free_text: "valid_free_text",
};

const firstNames = ["Nora", "Maya", "Adam", "Omar", "Lina", "Sam"];
const lastNames = ["Stone", "Rivera", "Saleh", "Carter", "Haddad", "Kim"];
const nullByte = Buffer.from([0]);
const mask64 = (1n << 64n) - 1n;

function generateRecords(
  contract: ContractJson,
  scenarioId: string,
  count: number,
  seed?: string,
): GeneratedRecord[] {
  if (!Number.isInteger(count) || count < 1) {
    throw new Error("count must be greater than 0");
  }

  const scenario = findScenario(contract, scenarioId);
  const baseSeed = seed ?? contract.generation.defaultSeed;
  return Array.from({ length: count }, (_, index) =>
    generateRecord(contract, scenario, scenarioId, baseSeed, index),
  );
}

function generateRecord(
  contract: ContractJson,
  scenario: ScenarioDefinition,
  scenarioId: string,
  seed: string,
  index: number,
): GeneratedRecord {
  const record: GeneratedRecord = {};

  for (const [fieldName, field] of Object.entries(contract.fields)) {
    const override = scenario.fields[fieldName] ?? {};
    if (Object.hasOwn(override, "value")) {
      record[fieldName] = override.value;
      continue;
    }

    const strategy = override.strategy ?? defaultStrategy(field);
    if (strategy === "missing" || strategy === "missing_required") {
      continue;
    }

    record[fieldName] = runStrategy(field, strategy, seed, scenarioId, index, fieldName);
  }

  return record;
}

function findScenario(contract: ContractJson, scenarioId: string): ScenarioDefinition {
  const scenario = contract.scenarios.find((candidate) => candidate.id === scenarioId);
  if (!scenario) {
    throw new Error(`Unknown scenario: ${scenarioId}`);
  }
  return scenario;
}

function defaultStrategy(field: ContractField): string {
  const strategy = defaultStrategies[field.businessType];
  if (!strategy) {
    throw new Error(`No default strategy for business type: ${field.businessType}`);
  }
  return strategy;
}

function runStrategy(
  field: ContractField,
  strategy: string,
  seed: string,
  scenarioId: string,
  index: number,
  fieldName: string,
): unknown {
  const scope = `${scenarioId}:${fieldName}`;
  switch (strategy) {
    case "valid_first_name":
      return choice(field, seed, scope, index, firstNames);
    case "valid_last_name":
      return choice(field, seed, scope, index, lastNames);
    case "valid_full_name":
      return `${choice(field, seed, `${scope}:first`, index, firstNames)} ${choice(
        field,
        seed,
        `${scope}:last`,
        index,
        lastNames,
      )}`;
    case "valid_username":
      return `user_${randomInt(field, seed, scope, index, 1000, 9999)}`;
    case "valid_email":
      return `user${index}.${randomInt(field, seed, scope, index, 1000, 9999)}@example.test`;
    case "invalid_email_format":
      return "not-an-email";
    case "valid_phone":
      return validPhone(field, seed, scope, index);
    case "invalid_alpha":
      return "abc";
    case "valid_password":
      return `Tdf!${randomInt(field, seed, scope, index, 100000, 999999)}Pass`;
    case "valid_integer":
      return validInteger(field, seed, scope, index);
    case "valid_decimal":
      return validDecimal(field, seed, scope, index);
    case "valid_enum":
      return validEnum(field, seed, scope, index);
    case "valid_date":
      return validDate(field, seed, scope, index);
    case "valid_boolean":
      return randomInt(field, seed, scope, index, 0, 1) === 1;
    case "valid_free_text":
      return `Generated test note ${index + 1}`;
    default:
      throw new Error(`Unknown strategy: ${strategy}`);
  }
}

function validPhone(field: ContractField, seed: string, scope: string, index: number): string {
  const country = stringConstraint(field, "country", "US");
  const suffix = randomInt(field, seed, scope, index, 1000, 9999);
  return country === "US" ? `+155501${suffix}` : `+100000${suffix}`;
}

function validInteger(field: ContractField, seed: string, scope: string, index: number): number {
  const minimum = Math.trunc(numberConstraint(field, "minimum", 1));
  const maximum = Math.trunc(numberConstraint(field, "maximum", 999));
  return randomInt(field, seed, scope, index, minimum, maximum);
}

function validDecimal(field: ContractField, seed: string, scope: string, index: number): number {
  const minimum = numberConstraint(field, "minimum", 1);
  const maximum = numberConstraint(field, "maximum", 999);
  const value = minimum + rng(field, seed, scope, index).nextFloat() * (maximum - minimum);
  return Math.round(value * 100) / 100;
}

function validEnum(field: ContractField, seed: string, scope: string, index: number): unknown {
  const values = field.constraints?.values;
  if (!Array.isArray(values) || values.length === 0) {
    throw new Error("enum field requires constraints.values");
  }
  return values[rng(field, seed, scope, index).nextInt(0, values.length - 1)];
}

function validDate(field: ContractField, seed: string, scope: string, index: number): string {
  const days = randomInt(field, seed, scope, index, 0, 10_000);
  return new Date(Date.UTC(1990, 0, 1 + days)).toISOString().slice(0, 10);
}

function randomInt(
  field: ContractField,
  seed: string,
  scope: string,
  index: number,
  minimum: number,
  maximum: number,
): number {
  return rng(field, seed, scope, index).nextInt(minimum, maximum);
}

function choice<T>(field: ContractField, seed: string, scope: string, index: number, values: T[]): T {
  return values[rng(field, seed, scope, index).nextInt(0, values.length - 1)];
}

function rng(field: ContractField, seed: string, scope: string, index: number): DeterministicRandom {
  return new DeterministicRandom(stableSeed(seed, scope, field.businessType, index));
}

function numberConstraint(field: ContractField, name: string, fallback: number): number {
  const value = field.constraints?.[name];
  return typeof value === "number" ? value : fallback;
}

function stringConstraint(field: ContractField, name: string, fallback: string): string {
  const value = field.constraints?.[name];
  return typeof value === "string" ? value : fallback;
}

function stableSeed(...parts: unknown[]): bigint {
  const hash = createHash("sha256");
  for (const part of parts) {
    hash.update(String(part), "utf8");
    hash.update(nullByte);
  }

  const digest = hash.digest();
  let value = 0n;
  for (let index = 0; index < 8; index += 1) {
    value = (value << 8n) | BigInt(digest[index]);
  }
  return value;
}

class DeterministicRandom {
  private static readonly increment = 0x9e3779b97f4a7c15n;
  private static readonly mixA = 0xbf58476d1ce4e5b9n;
  private static readonly mixB = 0x94d049bb133111ebn;

  constructor(private state: bigint) {}

  nextInt(minimum: number, maximum: number): number {
    const bound = BigInt(maximum - minimum + 1);
    return minimum + Number(this.nextUInt64() % bound);
  }

  nextFloat(): number {
    return Number(this.nextUInt64() >> 11n) / 9007199254740992;
  }

  private nextUInt64(): bigint {
    this.state = (this.state + DeterministicRandom.increment) & mask64;
    let value = this.state;
    value = ((value ^ (value >> 30n)) * DeterministicRandom.mixA) & mask64;
    value = ((value ^ (value >> 27n)) * DeterministicRandom.mixB) & mask64;
    return (value ^ (value >> 31n)) & mask64;
  }
}
