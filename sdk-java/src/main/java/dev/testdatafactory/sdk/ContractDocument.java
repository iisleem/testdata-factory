package dev.testdatafactory.sdk;

import com.fasterxml.jackson.databind.JsonNode;

public final class ContractDocument {
    private final JsonNode root;
    private final String defaultSeed;

    ContractDocument(JsonNode root, String defaultSeed) {
        this.root = root;
        this.defaultSeed = defaultSeed;
    }

    public String id() {
        return root.path("id").asText();
    }

    public JsonNode raw() {
        return root;
    }

    public ScenarioRequest scenario(String scenarioId) {
        return new ScenarioRequest(this, scenarioId);
    }

    String defaultSeed() {
        return defaultSeed;
    }
}
