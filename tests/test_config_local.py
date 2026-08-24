"""Tests for the ignored local configuration overlay."""

from pathlib import Path

from mewcode.config import _merge_config, load_config


def test_merge_config_recursively_preserves_base_mappings():
    base = {"llm": {"models": {"demo": {"provider": "custom", "model": "demo"}}}}
    override = {"llm": {"models": {"demo": {"api_key": "local-key"}}}}

    merged = _merge_config(base, override)

    assert merged["llm"]["models"]["demo"] == {
        "provider": "custom",
        "model": "demo",
        "api_key": "local-key",
    }
    assert "api_key" not in base["llm"]["models"]["demo"]


def test_explicit_config_path_does_not_load_sibling_local_overlay(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("llm:\n  default_model: base\n", encoding="utf-8")
    (tmp_path / "config.local.yaml").write_text(
        "llm:\n  default_model: local\n", encoding="utf-8"
    )

    assert load_config(str(config_path))["llm"]["default_model"] == "base"
