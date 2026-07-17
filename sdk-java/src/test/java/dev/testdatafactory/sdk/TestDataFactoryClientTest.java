package dev.testdatafactory.sdk;

import org.junit.jupiter.api.Test;

import java.nio.file.Path;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class TestDataFactoryClientTest {
    private static final Path CONTRACT = Path.of("..", "examples", "contracts", "register.tdf.json");

    @Test
    void loadsContractFixture() {
        ContractDocument contract = TestDataFactory.local().seed("java-sdk").contract(CONTRACT);

        assertEquals("register", contract.id());
        assertEquals("java-sdk", TestDataFactory.local().seed("java-sdk").defaultSeed());
    }

    @Test
    void createsScenarioRequest() {
        ContractDocument contract = TestDataFactory.local().contract(CONTRACT);
        ScenarioRequest scenario = contract.scenario("valid_signup");

        assertEquals("valid_signup", scenario.scenarioId());
        assertEquals("register", scenario.contract().id());
    }

    @Test
    void generatesScenarioRecords() {
        List<Map<String, Object>> users = TestDataFactory.local()
            .seed("java-sdk")
            .contract(CONTRACT)
            .scenario("valid_signup")
            .count(2);

        assertEquals(2, users.size());
        Map<String, Object> first = users.get(0);
        assertEquals(
            List.of("firstName", "email", "phone", "password", "age", "plan", "birthDate", "newsletter"),
            List.copyOf(first.keySet())
        );
        assertTrue(first.get("email").toString().endsWith("@example.test"));
        assertTrue(first.get("phone").toString().startsWith("+155501"));
        assertTrue((Integer) first.get("age") >= 18);
        assertTrue((Integer) first.get("age") <= 99);
        assertTrue(List.of("basic", "pro", "enterprise").contains(first.get("plan")));
        assertTrue(first.get("newsletter") instanceof Boolean);
    }

    @Test
    void generationIsRepeatableForSameSeed() {
        List<Map<String, Object>> first = TestDataFactory.local()
            .seed("java-sdk")
            .contract(CONTRACT)
            .scenario("valid_signup")
            .count(2);
        List<Map<String, Object>> second = TestDataFactory.local()
            .seed("java-sdk")
            .contract(CONTRACT)
            .scenario("valid_signup")
            .count(2);
        List<Map<String, Object>> differentSeed = TestDataFactory.local()
            .seed("java-sdk-other")
            .contract(CONTRACT)
            .scenario("valid_signup")
            .count(2);

        assertEquals(first, second);
        assertNotEquals(first, differentSeed);
    }

    @Test
    void appliesNegativeScenarioStrategies() {
        Map<String, Object> user = TestDataFactory.local()
            .seed("java-sdk")
            .contract(CONTRACT)
            .scenario("invalid_email_format")
            .one();

        assertEquals("not-an-email", user.get("email"));
        assertTrue(user.get("password").toString().startsWith("Tdf!"));
    }

    @Test
    void unknownScenarioFailsClearly() {
        ScenarioRequest scenario = TestDataFactory.local().contract(CONTRACT).scenario("missing_scenario");

        IllegalArgumentException error = assertThrows(IllegalArgumentException.class, scenario::one);

        assertTrue(error.getMessage().contains("Unknown scenario: missing_scenario"));
    }
}
