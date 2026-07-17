package dev.testdatafactory.sdk;

public final class ScenarioRequest {
    private final ContractDocument contract;
    private final String scenarioId;

    ScenarioRequest(ContractDocument contract, String scenarioId) {
        this.contract = contract;
        this.scenarioId = scenarioId;
    }

    public ContractDocument contract() {
        return contract;
    }

    public String scenarioId() {
        return scenarioId;
    }
}
