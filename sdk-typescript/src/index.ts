import { readFileSync } from "node:fs";

export type ContractJson = {
  id: string;
  [key: string]: unknown;
};

export class ContractDocument {
  constructor(private readonly contractJson: ContractJson) {}

  id(): string {
    return this.contractJson.id;
  }

  raw(): ContractJson {
    return this.contractJson;
  }

  scenario(scenarioId: string): ScenarioRequest {
    return new ScenarioRequest(this, scenarioId);
  }
}

export class ScenarioRequest {
  constructor(
    private readonly contractDocument: ContractDocument,
    private readonly idValue: string,
  ) {}

  contract(): ContractDocument {
    return this.contractDocument;
  }

  scenarioId(): string {
    return this.idValue;
  }
}

export class TestDataFactoryClient {
  constructor(private readonly defaultSeedValue?: string) {}

  seed(seed: string): TestDataFactoryClient {
    return new TestDataFactoryClient(seed);
  }

  defaultSeed(): string | undefined {
    return this.defaultSeedValue;
  }

  contract(path: string): ContractDocument {
    const data = JSON.parse(readFileSync(path, "utf8")) as ContractJson;
    return new ContractDocument(data);
  }
}

export const testDataFactory = {
  local(): TestDataFactoryClient {
    return new TestDataFactoryClient();
  },
};
