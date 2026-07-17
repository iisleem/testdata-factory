package dev.testdatafactory.sdk;

import org.junit.jupiter.api.Test;

import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertEquals;

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
}
