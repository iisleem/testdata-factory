from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


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


class ModelProviderError(RuntimeError):
    """Raised when a local model provider cannot return structured JSON."""


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
    timeout_seconds: float = 60.0


@dataclass(frozen=True)
class ModelRuntimeConfig:
    model_profile: str
    provider: ProviderConfig


@dataclass(frozen=True)
class OllamaProvider:
    base_url: str
    model: str
    timeout_seconds: float = 60.0
    provider_type: str = "ollama"

    def chat_json(self, messages: list[dict[str, str]], response_schema: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": response_schema,
            "options": {"temperature": 0},
        }
        response = _post_json(_provider_url(self.base_url, "/api/chat"), payload, timeout_seconds=self.timeout_seconds)
        message = response.get("message")
        if not isinstance(message, dict):
            raise ModelProviderError("Ollama response did not include message content.")
        content = message.get("content")
        if not isinstance(content, str):
            raise ModelProviderError("Ollama response message content was not a string.")
        return _parse_model_json(content, provider_type=self.provider_type)


@dataclass(frozen=True)
class OpenAICompatibleProvider:
    base_url: str
    model: str
    timeout_seconds: float = 60.0
    provider_type: str = "openai_compatible"

    def chat_json(self, messages: list[dict[str, str]], response_schema: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        response = _post_json(
            _provider_url(self.base_url, "/chat/completions"),
            payload,
            timeout_seconds=self.timeout_seconds,
        )
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ModelProviderError("OpenAI-compatible response did not include choices.")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ModelProviderError("OpenAI-compatible response choice was not an object.")
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ModelProviderError("OpenAI-compatible response did not include message content.")
        content = message.get("content")
        if not isinstance(content, str):
            raise ModelProviderError("OpenAI-compatible response message content was not a string.")
        return _parse_model_json(content, provider_type=self.provider_type)


def get_model_profile(name: str) -> dict[str, Any]:
    try:
        return MODEL_PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown model profile: {name}") from exc


def model_profiles_payload() -> dict[str, dict[str, Any]]:
    return dict(MODEL_PROFILES)


def load_model_runtime_config(path: str | Path, *, profile: str | None = None) -> ModelRuntimeConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise ValueError(f"AI config file not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in AI config file: {config_path}")
    return parse_model_runtime_config(data, profile=profile)


def parse_model_runtime_config(config: dict[str, Any], *, profile: str | None = None) -> ModelRuntimeConfig:
    selected_profile = str(profile or config.get("modelProfile") or "balanced")
    get_model_profile(selected_profile)

    provider_config = config.get("provider")
    if not isinstance(provider_config, dict):
        raise ValueError("provider config is required")

    return ModelRuntimeConfig(
        model_profile=selected_profile,
        provider=parse_provider_config(provider_config, profile=selected_profile),
    )


def parse_provider_config(config: dict[str, Any], *, profile: str | None = None) -> ProviderConfig:
    provider_type = str(config.get("type", ""))
    if provider_type not in SUPPORTED_PROVIDER_TYPES:
        raise ValueError(f"Unsupported provider type: {provider_type}")

    base_url = str(config.get("baseUrl", "")).strip()
    profile_config = _profile_provider_config(config, profile)
    model = str(profile_config.get("model") or config.get("model", "")).strip()
    timeout_seconds = _timeout_seconds(profile_config.get("timeoutSeconds", config.get("timeoutSeconds", 60.0)))
    if not base_url:
        raise ValueError("provider.baseUrl is required")
    if not model:
        raise ValueError("provider.model is required")

    return ProviderConfig(
        provider_type=provider_type,
        base_url=base_url.rstrip("/"),
        model=model,
        timeout_seconds=timeout_seconds,
    )


def create_provider(config: ProviderConfig) -> LocalModelProvider:
    if config.provider_type == "ollama":
        return OllamaProvider(base_url=config.base_url, model=config.model, timeout_seconds=config.timeout_seconds)
    if config.provider_type == "openai_compatible":
        return OpenAICompatibleProvider(
            base_url=config.base_url,
            model=config.model,
            timeout_seconds=config.timeout_seconds,
        )
    raise ValueError(f"Unsupported provider type: {config.provider_type}")


def _profile_provider_config(config: dict[str, Any], profile: str | None) -> dict[str, Any]:
    if not profile:
        return {}
    profiles = config.get("profiles", {})
    if profiles is None:
        return {}
    if not isinstance(profiles, dict):
        raise ValueError("provider.profiles must be an object")
    profile_config = profiles.get(profile, {})
    if profile_config is None:
        return {}
    if not isinstance(profile_config, dict):
        raise ValueError(f"provider.profiles.{profile} must be an object")
    return profile_config


def _timeout_seconds(value: Any) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("provider.timeoutSeconds must be a number") from exc
    if timeout <= 0:
        raise ValueError("provider.timeoutSeconds must be greater than 0")
    return timeout


def _provider_url(base_url: str, path: str) -> str:
    return urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/"))


def _post_json(url: str, payload: dict[str, Any], *, timeout_seconds: float) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"content-type": "application/json", "accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ModelProviderError(f"Model provider request failed with HTTP {exc.code}: {_shorten(detail)}") from exc
    except URLError as exc:
        raise ModelProviderError(f"Model provider request failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise ModelProviderError("Model provider request timed out.") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ModelProviderError("Model provider returned invalid JSON.") from exc
    if not isinstance(data, dict):
        raise ModelProviderError("Model provider response was not a JSON object.")
    return data


def _parse_model_json(content: str, *, provider_type: str) -> dict[str, Any]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ModelProviderError(f"{provider_type} model response was not valid JSON.") from exc
    if not isinstance(data, dict):
        raise ModelProviderError(f"{provider_type} model response must be a JSON object.")
    return data


def _shorten(value: str, *, limit: int = 240) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit - 3]}..."
