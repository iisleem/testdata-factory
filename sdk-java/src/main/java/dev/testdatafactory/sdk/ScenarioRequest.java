package dev.testdatafactory.sdk;

import java.util.List;
import java.util.Map;

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

    public Map<String, Object> one() {
        return count(1).get(0);
    }

    public List<Map<String, Object>> count(int count) {
        return LocalGenerator.generate(contract.raw(), scenarioId, count, contract.defaultSeed());
    }
}
