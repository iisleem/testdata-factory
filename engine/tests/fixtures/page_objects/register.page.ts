import type { Locator, Page } from "@playwright/test";

export class RegisterPage {
  readonly emailInput: Locator;
  readonly passwordInput = this.page.locator('input[type="password"][name="password"][minlength="12"][maxlength="72"]');
  readonly mobilePhoneField = this.page.getByPlaceholder("Mobile phone");
  readonly spendLimitInput = this.page.locator('input[type="number"][name="spendLimit"][min="0"][max="500"]');
  readonly submitButton = this.page.getByRole("button", { name: "Create account" });

  constructor(private readonly page: Page) {
    this.emailInput = page.getByLabel("Work email");
  }

  async fillWebsite(website: string) {
    await this.page.fill('input[type="url"][name="website"]', website);
  }
}
