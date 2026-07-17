import { strict as assert } from "node:assert";
import { test } from "node:test";

import { testDataFactory } from "../src/index.js";

const contractPath = "../examples/contracts/register.tdf.json";

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
