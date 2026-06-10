"""Tests for environment-first model API key resolution."""

from mewcode.config import get_model_config


def _config(api_key: str = "plain-key", api_key_env: str | None = None) -> dict:
    model = {
        "provider": "custom",
        "base_url": "https://example.test/v1",
        "api_key": api_key,
        "api_format": "openai",
        "model": "demo-model",
    }
    if api_key_env is not None:
        model["api_key_env"] = api_key_env
    return {"llm": {"models": {"demo-model": model}}}


def test_api_key_env_overrides_plaintext(monkeypatch):
    monkeypatch.setenv("MEWCODE_TEST_API_KEY", "env-key")

    resolved = get_model_config(
        _config(api_key="plain-key", api_key_env="MEWCODE_TEST_API_KEY"),
        "demo-model",
    )

    assert resolved["api_key"] == "env-key"


def test_plaintext_api_key_used_when_env_missing(monkeypatch):
    monkeypatch.delenv("MEWCODE_TEST_API_KEY", raising=False)

    resolved = get_model_config(
        _config(api_key="plain-key", api_key_env="MEWCODE_TEST_API_KEY"),
        "demo-model",
    )

    assert resolved["api_key"] == "plain-key"


def test_empty_env_value_falls_back_to_plaintext(monkeypatch):
    monkeypatch.setenv("MEWCODE_TEST_API_KEY", "")

    resolved = get_model_config(
        _config(api_key="plain-key", api_key_env="MEWCODE_TEST_API_KEY"),
        "demo-model",
    )

    assert resolved["api_key"] == "plain-key"


def test_plaintext_key_without_env_field_still_works():
    resolved = get_model_config(_config(api_key="plain-key"), "demo-model")

    assert resolved["api_key"] == "plain-key"


def test_get_model_config_does_not_mutate_source_config(monkeypatch):
    monkeypatch.setenv("MEWCODE_TEST_API_KEY", "env-key")
    config = _config(api_key="plain-key", api_key_env="MEWCODE_TEST_API_KEY")

    resolved = get_model_config(config, "demo-model")

    assert resolved["api_key"] == "env-key"
    assert (
        config["llm"]["models"]["demo-model"]["api_key"]
        == "plain-key"
    )
