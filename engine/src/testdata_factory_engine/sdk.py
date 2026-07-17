from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .contracts import Contract, load_contract
from .generation import generate_records


class TestDataFactory:
    @staticmethod
    def local() -> TestDataFactoryClient:
        return TestDataFactoryClient()


@dataclass(frozen=True)
class TestDataFactoryClient:
    default_seed: str | None = None

    def seed(self, seed: str) -> TestDataFactoryClient:
        return TestDataFactoryClient(default_seed=seed)

    def contract(self, path: str | Path) -> ContractSession:
        return ContractSession(contract=load_contract(path), default_seed=self.default_seed)


@dataclass(frozen=True)
class ContractSession:
    contract: Contract
    default_seed: str | None = None

    def scenario(self, scenario_id: str) -> ScenarioSession:
        return ScenarioSession(contract=self.contract, scenario_id=scenario_id, default_seed=self.default_seed)


@dataclass(frozen=True)
class ScenarioSession:
    contract: Contract
    scenario_id: str
    default_seed: str | None = None

    def count(self, count: int) -> list[dict[str, object]]:
        return generate_records(self.contract, self.scenario_id, count=count, seed=self.default_seed)

    def one(self) -> dict[str, object]:
        return self.count(1)[0]
