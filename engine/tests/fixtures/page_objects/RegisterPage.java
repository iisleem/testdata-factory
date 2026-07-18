package fixtures.pageobjects;

import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.FindBy;

public class RegisterPage {
    private final WebDriver driver;

    @FindBy(css = "input[type='email'][name='email'][required]")
    private WebElement emailInput;

    private final By passwordInput = By.cssSelector("input[type='password'][name='password'][minlength='12'][maxlength='72']");
    private final By mobilePhoneField = By.name("mobilePhone");
    private final By spendLimitInput = By.cssSelector("input[type='number'][name='spendLimit'][min='0'][max='500']");

    public RegisterPage(WebDriver driver) {
        this.driver = driver;
    }

    public void fillWebsite(String website) {
        driver.findElement(By.cssSelector("input[type='url'][name='website']")).sendKeys(website);
    }

    public void submit() {
        driver.findElement(By.cssSelector("button[type='submit']")).click();
    }
}
