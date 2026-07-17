from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


MODEL_PROFILES = {
    "light": {
        "accuracy": "lower",
        "hardware": "low",
        "examples": ["qwen3:4b", "llama3.2:3b", "phi4-mini"],
    },
    "balanced": {
        "accuracy": "medium",
        "hardware": "moderate",
        "examples": ["qwen3:14b", "mistral-nemo", "gemma3:12b"],
    },
    "strong": {
        "accuracy": "high",
        "hardware": "high",
        "examples": ["qwen3:32b", "deepseek-r1:32b", "gemma3:27b"],
    },
}

SUPPORTED_PROVIDER_TYPES = {"ollama", "openai_compatible"}


class LocalModelProvider(Protocol):
    provider_type: str
    base_url: str
    model: str

    def chat_json(self, messages: list[dict[str, str]], response_schema: dict[str, Any]) -> dict[str, Any]:
        """Request a structured JSON response from a local model runtime."""


@dataclass(frozen=True)
class ProviderConfig:
    provider_type: str
    base_url: str
    model: str


@dataclass(frozen=True)
class OllamaProvider:
    base_url: str
    model: str
    provider_type: str = "ollama"

    def chat_json(self, messages: list[dict[str, str]], response_schema: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("Ollama requests are not implemented in this foundation slice.")


@dataclass(frozen=True)
class OpenAICompatibleProvider:
    base_url: str
    model: str
    provider_type: str = "openai_compatible"

    def chat_json(self, messages: list[dict[str, str]], response_schema: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("OpenAI-compatible requests are not implemented in this foundation slice.")


def get_model_profile(name: str) -> dict[str, Any]:
    try:
        return MODEL_PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown model profile: {name}") from exc


def model_profiles_payload() -> dict[str, dict[str, Any]]:
    return dict(MODEL_PROFILES)


def parse_provider_config(config: dict[str, Any]) -> ProviderConfig:
    provider_type = str(config.get("type", ""))
    if provider_type not in SUPPORTED_PROVIDER_TYPES:
        raise ValueError(f"Unsupported provider type: {provider_type}")

    base_url = str(config.get("baseUrl", "")).strip()
    model = str(config.get("model", "")).strip()
    if not base_url:
        raise ValueError("provider.baseUrl is required")
    if not model:
        raise ValueError("provider.model is required")

    return ProviderConfig(provider_type=provider_type, base_url=base_url, model=model)


def create_provider(config: ProviderConfig) -> LocalModelProvider:
    if config.provider_type == "ollama":
        return OllamaProvider(base_url=config.base_url, model=config.model)
    if config.provider_type == "openai_compatible":
        return OpenAICompatibleProvider(base_url=config.base_url, model=config.model)
    raise ValueError(f"Unsupported provider type: {config.provider_type}")
