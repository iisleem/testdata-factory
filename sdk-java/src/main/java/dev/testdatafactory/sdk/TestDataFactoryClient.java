package dev.testdatafactory.sdk;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.nio.file.Path;

public final class TestDataFactoryClient {
    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();

    private final String defaultSeed;

    TestDataFactoryClient(String defaultSeed) {
        this.defaultSeed = defaultSeed;
    }

    public TestDataFactoryClient seed(String seed) {
        return new TestDataFactoryClient(seed);
    }

    public String defaultSeed() {
        return defaultSeed;
    }

    public ContractDocument contract(Path path) {
        try {
            JsonNode root = OBJECT_MAPPER.readTree(path.toFile());
            return new ContractDocument(root);
        } catch (IOException exc) {
            throw new IllegalArgumentException("Unable to load contract: " + path, exc);
        }
    }
}
