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
