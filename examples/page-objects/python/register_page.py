from selenium.webdriver.common.by import By


class RegisterPage:
    def __init__(self, page, driver):
        self.page = page
        self.driver = driver
        self.email_input = page.get_by_label("Work email")
        self.password_input = page.locator('input[type="password"][name="password"][minlength="12"][maxlength="72"]')
        self.mobile_phone_field = (By.NAME, "mobilePhone")
        self.spend_limit_input = page.locator('input[type="number"][name="spendLimit"][min="0"][max="500"]')
        self.submit_button = page.get_by_role("button", name="Create account")

    def fill_website(self, website):
        self.page.fill('input[type="url"][name="website"]', website)
