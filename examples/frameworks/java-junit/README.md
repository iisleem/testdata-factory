# Java JUnit 5 Example

This source-tree friendly JUnit 5 example uses the Java SDK API from this repository. Copy the test class into a Maven or Gradle test source set that depends on the local `sdk-java` module or on a locally built SDK artifact.

For example, build the SDK from the repository root before wiring it into your application test project:

```bash
mvn -f sdk-java/pom.xml test
```

```java
package example;

import dev.testdatafactory.sdk.ContractDocument;
import dev.testdatafactory.sdk.TestDataFactory;
import org.junit.jupiter.api.Test;

import java.nio.file.Path;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class RegisterDataTest {
    private static final Path CONTRACT = Path.of("examples", "contracts", "register.tdf.json");

    @Test
    void validSignupDataFeedsHappyPathTests() {
        ContractDocument contract = TestDataFactory
            .local()
            .seed("junit-registration-flow")
            .contract(CONTRACT);

        List<Map<String, Object>> users = contract
            .scenario("valid_signup")
            .count(2);

        assertEquals(2, users.size());
        assertTrue(users.get(0).get("email").toString().endsWith("@example.test"));
        assertTrue(users.get(0).get("phone").toString().startsWith("+155501"));
        assertTrue(List.of("basic", "pro", "enterprise").contains(users.get(0).get("plan")));
    }

    @Test
    void invalidEmailDataFeedsNegativeValidationTests() {
        Map<String, Object> user = TestDataFactory
            .local()
            .seed("junit-registration-flow")
            .contract(CONTRACT)
            .scenario("invalid_email_format")
            .one();

        assertEquals("not-an-email", user.get("email"));
        assertTrue(user.get("password").toString().startsWith("Tdf!"));
    }
}
```
