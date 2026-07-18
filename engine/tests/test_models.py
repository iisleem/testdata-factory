from __future__ import annotations

import json
from pathlib import Path
from urllib.error import URLError

import pytest

from testdata_factory_engine.models import (
    ModelProviderError,
    OllamaProvider,
    OpenAICompatibleProvider,
    create_provider,
    get_model_profile,
    load_model_runtime_config,
    model_profiles_payload,
    parse_model_runtime_config,
    parse_provider_config,
)


def test_model_profiles_include_expected_tiers() -> None:
    assert set(model_profiles_payload()) == {"light", "balanced", "strong"}
    assert get_model_profile("balanced")["hardware"] == "moderate"


def test_unknown_model_profile_fails_clearly() -> None:
    with pytest.raises(ValueError, match="Unknown model profile"):
        get_model_profile("tiny")


def test_parse_ollama_provider_config() -> None:
    config = parse_provider_config(
        {
            "type": "ollama",
            "baseUrl": "http://localhost:11434",
            "model": "qwen3:14b",
        }
    )

    provider = create_provider(config)

    assert isinstance(provider, OllamaProvider)
    assert provider.base_url == "http://localhost:11434"
    assert provider.model == "qwen3:14b"


def test_parse_openai_compatible_provider_config() -> None:
    config = parse_provider_config(
        {
            "type": "openai_compatible",
            "baseUrl": "http://localhost:8080/v1",
            "model": "local-model",
        }
    )

    provider = create_provider(config)

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.base_url == "http://localhost:8080/v1"
    assert provider.model == "local-model"


def test_parse_provider_config_requires_supported_type() -> None:
    with pytest.raises(ValueError, match="Unsupported provider type"):
        parse_provider_config({"type": "cloud", "baseUrl": "http://localhost:11434", "model": "qwen3:14b"})


def test_parse_provider_config_requires_model() -> None:
    with pytest.raises(ValueError, match="provider.model is required"):
        parse_provider_config({"type": "ollama", "baseUrl": "http://localhost:11434"})


def test_parse_model_runtime_config_selects_profile_model() -> None:
    runtime = parse_model_runtime_config(
        {
            "modelProfile": "balanced",
            "provider": {
                "type": "ollama",
                "baseUrl": "http://localhost:11434/",
                "model": "qwen3:14b",
                "profiles": {
                    "light": {"model": "qwen3:4b"},
                    "strong": {"model": "qwen3:32b", "timeoutSeconds": 120},
                },
            },
        },
        profile="strong",
    )

    assert runtime.model_profile == "strong"
    assert runtime.provider.model == "qwen3:32b"
    assert runtime.provider.timeout_seconds == 120
    assert runtime.provider.base_url == "http://localhost:11434"


def test_load_model_runtime_config_reports_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="AI config file not found"):
        load_model_runtime_config(tmp_path / "missing.json")


def test_ollama_provider_posts_chat_and_parses_json(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout: float):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _HTTPResponse({"message": {"content": json.dumps({"status": "ok"})}})

    monkeypatch.setattr("testdata_factory_engine.models.urlopen", fake_urlopen)

    provider = OllamaProvider(base_url="http://localhost:11434", model="qwen3:4b", timeout_seconds=12)
    result = provider.chat_json(
        [{"role": "user", "content": "Return JSON."}],
        {"type": "object", "properties": {"status": {"type": "string"}}},
    )

    assert result == {"status": "ok"}
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["timeout"] == 12
    assert captured["payload"]["model"] == "qwen3:4b"
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["format"]["type"] == "object"


def test_ollama_provider_invalid_model_json_fails_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout: float):
        return _HTTPResponse({"message": {"content": "not-json"}})

    monkeypatch.setattr("testdata_factory_engine.models.urlopen", fake_urlopen)

    provider = OllamaProvider(base_url="http://localhost:11434", model="qwen3:4b")
    with pytest.raises(ModelProviderError, match="ollama model response was not valid JSON"):
        provider.chat_json([{"role": "user", "content": "Return JSON."}], {"type": "object"})


def test_provider_connection_failure_fails_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout: float):
        raise URLError("connection refused")

    monkeypatch.setattr("testdata_factory_engine.models.urlopen", fake_urlopen)

    provider = OllamaProvider(base_url="http://localhost:11434", model="qwen3:4b")
    with pytest.raises(ModelProviderError, match="Model provider request failed: connection refused"):
        provider.chat_json([{"role": "user", "content": "Return JSON."}], {"type": "object"})


class _HTTPResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")
