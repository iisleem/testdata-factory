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
  dependencies?: Record<string, unknown>;
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
  country_code: "valid_country_code",
  address_line: "valid_address_line",
  city: "valid_city",
  state: "valid_state",
  postal_code: "valid_postal_code",
  country: "valid_country",
  integer: "valid_integer",
  quantity: "valid_integer",
  decimal: "valid_decimal",
  amount: "valid_decimal",
  percentage: "valid_decimal",
  currency: "valid_currency",
  enum: "valid_enum",
  date: "valid_date",
  date_of_birth: "valid_date",
  time: "valid_time",
  datetime: "valid_datetime",
  boolean: "valid_boolean",
  url: "valid_url",
  domain: "valid_domain",
  uuid: "valid_uuid",
  national_id: "valid_national_id",
  passport_number: "valid_passport_number",
  tax_id: "valid_tax_id",
  account_number: "valid_account_number",
  iban: "valid_iban",
  credit_card_number: "valid_credit_card_number",
  cvv: "valid_cvv",
  expiry_date: "valid_expiry_date",
  otp: "valid_otp",
  free_text: "valid_free_text",
};

const firstNames = ["Nora", "Maya", "Adam", "Omar", "Lina", "Sam"];
const lastNames = ["Stone", "Rivera", "Saleh", "Carter", "Haddad", "Kim"];
const countryCodes = ["US", "CA", "GB", "AU", "DE", "FR", "JO"];
const cities = ["Springfield", "Riverton", "Fairview", "Georgetown", "Franklin"];
const states = ["CA", "NY", "TX", "WA", "IL", "FL"];
const countries = ["United States", "Canada", "United Kingdom", "Australia", "Germany", "France", "Jordan"];
const currencies = ["USD", "EUR", "GBP", "CAD", "AUD", "JPY", "JOD"];
const relationalStrategies = new Set([
  "match_field",
  "mismatch_field",
  "range_end_after_start",
  "date_after_related_field",
  "date_before_related_field",
  "numeric_max_at_or_above_min",
  "numeric_max_below_min",
]);
const independentValueStrategies = new Set([
  "xss_payload",
  "sql_injection_payload",
  "null_value",
  "empty_string",
  "whitespace_only",
  "over_max_length",
  "below_min_length",
  "duplicate_value",
]);
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

    let strategy = override.strategy ?? defaultStrategy(field);
    if (strategy === "missing" || strategy === "missing_required") {
      continue;
    }

    if (relationalStrategies.has(strategy)) {
      strategy = defaultStrategy(field);
    }

    record[fieldName] = runStrategy(field, strategy, seed, scenarioId, index, fieldName);
  }

  applyDependencies(record, contract, scenario);
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
    case "invalid_phone_format":
      return "not-a-phone";
    case "valid_country_code":
      return choice(field, seed, scope, index, countryCodes);
    case "valid_address_line":
      return validAddressLine(field, seed, scope, index);
    case "valid_city":
      return choice(field, seed, scope, index, cities);
    case "valid_state":
      return choice(field, seed, scope, index, states);
    case "valid_postal_code":
      return String(randomInt(field, seed, scope, index, 10000, 99999));
    case "valid_country":
      return choice(field, seed, scope, index, countries);
    case "invalid_alpha":
      return "abc";
    case "valid_password":
      return `Tdf!${randomInt(field, seed, scope, index, 100000, 999999)}Pass`;
    case "weak_password":
      return "password";
    case "valid_integer":
      return validInteger(field, seed, scope, index);
    case "valid_decimal":
      return validDecimal(field, seed, scope, index);
    case "valid_enum":
      return validEnum(field, seed, scope, index);
    case "valid_date":
      return validDate(field, seed, scope, index);
    case "valid_time":
      return validTime(field, seed, scope, index);
    case "valid_datetime":
      return validDatetime(field, seed, scope, index);
    case "valid_boolean":
      return randomInt(field, seed, scope, index, 0, 1) === 1;
    case "boolean_false":
      return false;
    case "boolean_true":
      return true;
    case "valid_currency":
      return choice(field, seed, scope, index, currencies);
    case "valid_url":
      return validUrl(field, seed, scope, index);
    case "valid_domain":
      return validDomain(field, seed, scope, index);
    case "valid_uuid":
      return validUuid(field, seed, scope, index);
    case "valid_national_id":
      return `NID-${randomInt(field, seed, scope, index, 100000000, 999999999)}`;
    case "valid_passport_number":
      return validPassportNumber(field, seed, scope, index);
    case "valid_tax_id":
      return `TAX-${randomInt(field, seed, scope, index, 10000000, 99999999)}`;
    case "valid_account_number":
      return `000${randomInt(field, seed, scope, index, 100000000, 999999999)}`;
    case "valid_iban":
      return validIban(field, seed, scope, index);
    case "valid_credit_card_number":
      return validCreditCardNumber(field, seed, scope, index);
    case "valid_cvv":
      return randomInt(field, seed, scope, index, 0, 999).toString().padStart(3, "0");
    case "valid_expiry_date":
      return validExpiryDate(field, seed, scope, index);
    case "valid_otp":
      return randomInt(field, seed, scope, index, 0, 999999).toString().padStart(6, "0");
    case "valid_free_text":
      return `Generated test note ${index + 1}`;
    case "xss_payload":
      return "<script>alert('tdf')</script>";
    case "sql_injection_payload":
      return "admin' OR '1'='1";
    case "null_value":
      return null;
    case "empty_string":
      return "";
    case "whitespace_only":
      return "   ";
    case "over_max_length":
      return overMaxLength(field);
    case "below_min_length":
      return belowMinLength(field);
    case "duplicate_value":
      return duplicateValue(field);
    default:
      throw new Error(`Unknown strategy: ${strategy}`);
  }
}

function validAddressLine(field: ContractField, seed: string, scope: string, index: number): string {
  const random = rng(field, seed, scope, index);
  const streets = ["Market Street", "Cedar Avenue", "River Road", "Summit Lane", "Atlas Way"];
  return `${random.nextInt(100, 999)} ${streets[random.nextInt(0, streets.length - 1)]}`;
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

function validTime(field: ContractField, seed: string, scope: string, index: number): string {
  const random = rng(field, seed, scope, index);
  return `${random.nextInt(0, 23).toString().padStart(2, "0")}:${random
    .nextInt(0, 59)
    .toString()
    .padStart(2, "0")}:00`;
}

function validDatetime(field: ContractField, seed: string, scope: string, index: number): string {
  const random = rng(field, seed, scope, index);
  const value = new Date(Date.UTC(2024, 0, 1, 9, random.nextInt(0, 8 * 60), 0));
  value.setUTCDate(value.getUTCDate() + random.nextInt(0, 365));
  return value.toISOString().replace(".000Z", "Z");
}

function validUrl(field: ContractField, seed: string, scope: string, index: number): string {
  return `https://app-${randomInt(field, seed, scope, index, 100, 999)}.example.test/resource-${index + 1}`;
}

function validDomain(field: ContractField, seed: string, scope: string, index: number): string {
  return `service-${randomInt(field, seed, scope, index, 100, 999)}.example.test`;
}

function validUuid(field: ContractField, seed: string, scope: string, index: number): string {
  const digest = createHash("sha256")
    .update(`${seed}:${scope}:${field.businessType}:${index}`, "utf8")
    .digest();
  const bytes = Buffer.from(digest.subarray(0, 16));
  bytes[6] = (bytes[6] & 0x0f) | 0x50;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = bytes.toString("hex");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function validPassportNumber(field: ContractField, seed: string, scope: string, index: number): string {
  const random = rng(field, seed, scope, index);
  const prefixes = ["P", "T", "X"];
  return `${prefixes[random.nextInt(0, prefixes.length - 1)]}${random.nextInt(10000000, 99999999)}`;
}

function validIban(field: ContractField, seed: string, scope: string, index: number): string {
  const bban = `TEST123456${randomInt(field, seed, scope, index, 0, 99999999).toString().padStart(8, "0")}`;
  return `GB${ibanCheckDigits("GB", bban)}${bban}`;
}

function validCreditCardNumber(field: ContractField, seed: string, scope: string, index: number): string {
  const body = `411111${randomInt(field, seed, scope, index, 0, 999999999).toString().padStart(9, "0")}`;
  return `${body}${luhnCheckDigit(body)}`;
}

function validExpiryDate(field: ContractField, seed: string, scope: string, index: number): string {
  const random = rng(field, seed, scope, index);
  const month = random.nextInt(1, 12).toString().padStart(2, "0");
  const year = (30 + random.nextInt(0, 9)).toString().padStart(2, "0");
  return `${month}/${year}`;
}

function overMaxLength(field: ContractField): string {
  const maximum = integerConstraint(field, "maxLength");
  const length = maximum !== undefined && maximum >= 0 ? maximum + 1 : 256;
  return "X".repeat(length);
}

function belowMinLength(field: ContractField): string {
  const minimum = integerConstraint(field, "minLength");
  const length = minimum !== undefined && minimum > 0 ? minimum - 1 : 0;
  return "A".repeat(length);
}

function duplicateValue(field: ContractField): unknown {
  switch (field.businessType) {
    case "email":
      return boundedEmail(field, "duplicate@example.test");
    case "username":
      return boundedText(field, "duplicate_user");
    case "uuid":
      return "00000000-0000-4000-8000-000000000000";
    case "integer":
    case "quantity":
      return integerMinimum(field);
    case "decimal":
    case "amount":
    case "percentage":
      return numericMinimum(field);
    case "date":
    case "date_of_birth":
      return "2026-01-01";
    default:
      return boundedText(field, "duplicate");
  }
}

function applyDependencies(
  record: GeneratedRecord,
  contract: ContractJson,
  scenario: ScenarioDefinition,
): void {
  for (const [fieldName, field] of Object.entries(contract.fields)) {
    if (!Object.hasOwn(record, fieldName)) {
      continue;
    }

    const override = scenario.fields[fieldName] ?? {};
    if (Object.hasOwn(override, "value")) {
      continue;
    }

    const dependencies = field.dependencies;
    if (!isRecord(dependencies)) {
      continue;
    }

    const strategy = typeof override.strategy === "string" ? override.strategy : "";
    if (independentValueStrategies.has(strategy)) {
      continue;
    }

    const matchesField = dependencies.matchesField;
    if (typeof matchesField === "string" && Object.hasOwn(record, matchesField)) {
      record[fieldName] =
        strategy === "mismatch_field" ? differentValue(record[matchesField], field) : record[matchesField];
      continue;
    }

    const rangeStart = dependencies.rangeEndFor;
    if (typeof rangeStart === "string" && Object.hasOwn(record, rangeStart)) {
      record[fieldName] = relativeTemporalValue(
        record[rangeStart],
        field,
        strategy === "date_before_related_field" ? -1 : 7,
      );
      continue;
    }

    const numericMinimum = dependencies.maxFor;
    if (typeof numericMinimum === "string" && Object.hasOwn(record, numericMinimum)) {
      record[fieldName] =
        strategy === "numeric_max_below_min"
          ? relativeNumericValue(record[numericMinimum], field, -1)
          : validNumericMaxValue(record[numericMinimum], field);
    }
  }
}

function differentValue(value: unknown, field: ContractField): unknown {
  if (value === null || value === undefined) {
    return boundedText(field, "mismatch");
  }
  if (typeof value === "boolean") {
    return !value;
  }
  if (typeof value === "number") {
    return Number.isInteger(value) ? value + 1 : Math.round((value + 1) * 100) / 100;
  }

  const original = String(value);
  const candidate = boundedText(field, `${original}_mismatch`, "X");
  if (candidate !== original) {
    return candidate;
  }
  if (!original) {
    return boundedText(field, "mismatch");
  }
  const replacement = original.endsWith("X") ? "Y" : "X";
  return `${original.slice(0, -1)}${replacement}`;
}

function relativeTemporalValue(value: unknown, field: ContractField, days: number): string {
  const parsed = parseTemporalValue(value) ?? new Date(Date.UTC(2026, 0, 1, 9, 0, 0));
  const shifted = new Date(parsed.getTime());
  shifted.setUTCDate(shifted.getUTCDate() + days);
  return field.dataType === "datetime" ? formatDateTimeZ(shifted) : shifted.toISOString().slice(0, 10);
}

function parseTemporalValue(value: unknown): Date | undefined {
  if (typeof value !== "string" || !value) {
    return undefined;
  }

  const normalized = value.endsWith("Z") ? value.slice(0, -1) : value;
  if (normalized.includes("T")) {
    const match =
      /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?$/.exec(normalized);
    if (!match) {
      return undefined;
    }
    return validUtcDate(
      Number(match[1]),
      Number(match[2]),
      Number(match[3]),
      Number(match[4]),
      Number(match[5]),
      Number(match[6] ?? 0),
    );
  }

  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(normalized);
  if (!match) {
    return undefined;
  }
  return validUtcDate(Number(match[1]), Number(match[2]), Number(match[3]), 9, 0, 0);
}

function validUtcDate(
  year: number,
  month: number,
  day: number,
  hour: number,
  minute: number,
  second: number,
): Date | undefined {
  const value = new Date(Date.UTC(year, month - 1, day, hour, minute, second));
  if (
    value.getUTCFullYear() !== year ||
    value.getUTCMonth() !== month - 1 ||
    value.getUTCDate() !== day ||
    value.getUTCHours() !== hour ||
    value.getUTCMinutes() !== minute ||
    value.getUTCSeconds() !== second
  ) {
    return undefined;
  }
  return value;
}

function formatDateTimeZ(value: Date): string {
  return `${value.getUTCFullYear().toString().padStart(4, "0")}-${(value.getUTCMonth() + 1)
    .toString()
    .padStart(2, "0")}-${value.getUTCDate().toString().padStart(2, "0")}T${value
    .getUTCHours()
    .toString()
    .padStart(2, "0")}:${value.getUTCMinutes().toString().padStart(2, "0")}:${value
    .getUTCSeconds()
    .toString()
    .padStart(2, "0")}Z`;
}

function validNumericMaxValue(value: unknown, field: ContractField): number {
  const base = numberValue(value) ?? numericMinimum(field);
  const step = numericStep(field);
  let candidate = base + step;
  const maximum = numberConstraintValue(field, "maximum");
  if (maximum !== undefined && candidate > maximum && maximum >= base) {
    candidate = maximum;
  } else if (maximum !== undefined && maximum < base) {
    candidate = base;
  }

  const minimum = numberConstraintValue(field, "minimum");
  if (minimum !== undefined && candidate < minimum) {
    candidate = minimum;
  }

  return coerceNumberForField(candidate, field);
}

function relativeNumericValue(value: unknown, field: ContractField, offset: number): number {
  const base = numberValue(value) ?? numericMinimum(field);
  return coerceNumberForField(base + offset * numericStep(field), field);
}

function numberValue(value: unknown): number | undefined {
  return typeof value === "number" ? value : undefined;
}

function numericStep(field: ContractField): number {
  const step = field.constraints?.step || field.constraints?.multipleOf;
  return typeof step === "number" && step > 0 ? step : 1;
}

function integerMinimum(field: ContractField): number {
  return Math.trunc(numericMinimum(field));
}

function numericMinimum(field: ContractField): number {
  return numberConstraintValue(field, "minimum") ?? 1;
}

function coerceNumberForField(value: number, field: ContractField): number {
  if (field.dataType === "integer") {
    return Math.trunc(value);
  }
  return Math.round(value * 100) / 100;
}

function boundedText(field: ContractField, value: string, filler = "x"): string {
  const maximum = integerConstraint(field, "maxLength");
  if (maximum !== undefined && maximum >= 0 && value.length > maximum) {
    value = value.slice(0, maximum);
  }

  const minimum = integerConstraint(field, "minLength");
  if (minimum !== undefined && value.length < minimum) {
    value += filler.repeat(minimum - value.length);
  }
  return value;
}

function boundedEmail(field: ContractField, value: string): string {
  const maximum = integerConstraint(field, "maxLength");
  if (maximum !== undefined && maximum >= 5 && maximum < value.length) {
    value = maximum < "a@example.test".length ? "a@b.c" : "a@example.test";
  }

  const minimum = integerConstraint(field, "minLength");
  if (minimum !== undefined && value.length < minimum) {
    value = `${"a".repeat(Math.max(0, minimum - "@example.test".length))}@example.test`;
  }
  return value;
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
  return numberConstraintValue(field, name) ?? fallback;
}

function stringConstraint(field: ContractField, name: string, fallback: string): string {
  const value = field.constraints?.[name];
  return typeof value === "string" ? value : fallback;
}

function numberConstraintValue(field: ContractField, name: string): number | undefined {
  const value = field.constraints?.[name];
  return typeof value === "number" ? value : undefined;
}

function integerConstraint(field: ContractField, name: string): number | undefined {
  const value = numberConstraintValue(field, name);
  return value !== undefined && Number.isInteger(value) ? value : undefined;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function ibanCheckDigits(countryCode: string, bban: string): string {
  const remainder = ibanMod97(`${bban}${countryCode}00`);
  return String(98 - remainder).padStart(2, "0");
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
      continue;
    }
    for (const digit of digits) {
      remainder = (remainder * 10 + Number(digit)) % 97;
    }
  }
  return remainder;
}

function luhnCheckDigit(number: string): string {
  let total = 0;
  const reversed = [...number].reverse();
  for (let index = 0; index < reversed.length; index += 1) {
    let digit = Number(reversed[index]);
    if (index % 2 === 0) {
      digit *= 2;
      if (digit > 9) {
        digit -= 9;
      }
    }
    total += digit;
  }
  return String((10 - (total % 10)) % 10);
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
