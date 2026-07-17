package dev.testdatafactory.sdk;

import com.fasterxml.jackson.databind.JsonNode;

public final class ContractDocument {
    private final JsonNode root;

    ContractDocument(JsonNode root) {
        this.root = root;
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
}
