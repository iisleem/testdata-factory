import { expect, test } from "@playwright/test";

import { testDataFactory } from "../../../sdk-typescript/dist/src/index.js";

const contractPath = "examples/contracts/register.tdf.json";

test("registration accepts generated happy-path data", async ({ page }) => {
  const user = testDataFactory
    .local()
    .seed("playwright-registration-flow")
    .contract(contractPath)
    .scenario("valid_signup")
    .one();

  await page.goto("/register");
  await page.getByLabel("First name").fill(String(user.firstName));
  await page.getByLabel("Email").fill(String(user.email));
  await page.getByLabel("Phone").fill(String(user.phone));
  await page.getByLabel("Password").fill(String(user.password));
  await page.getByLabel("Plan").selectOption(String(user.plan));
  await page.getByRole("button", { name: "Create account" }).click();

  await expect(page.getByText("Account created")).toBeVisible();
});

test("registration rejects generated invalid email data", async ({ page }) => {
  const user = testDataFactory
    .local()
    .seed("playwright-registration-flow")
    .contract(contractPath)
    .scenario("invalid_email_format")
    .one();

  await page.goto("/register");
  await page.getByLabel("First name").fill(String(user.firstName));
  await page.getByLabel("Email").fill(String(user.email));
  await page.getByLabel("Password").fill(String(user.password));
  await page.getByRole("button", { name: "Create account" }).click();

  await expect(page.getByText("Enter a valid email address")).toBeVisible();
});
