package dev.testdatafactory.sdk;

public final class TestDataFactory {
    private TestDataFactory() {
    }

    public static TestDataFactoryClient local() {
        return new TestDataFactoryClient(null);
    }
}
