from __future__ import annotations

import pytest

from testdata_factory_engine.models import (
    OllamaProvider,
    OpenAICompatibleProvider,
    create_provider,
    get_model_profile,
    model_profiles_payload,
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
