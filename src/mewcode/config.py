"""Configuration loader for MewCode"""

import os
from pathlib import Path
from typing import Any, Optional

import yaml


_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"
_LOCAL_CONFIG_SUFFIX = ".local.yaml"


def _merge_config(base: dict, override: dict) -> dict:
    """Return a recursive merge without mutating either input mapping."""
    merged = dict(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _merge_config(current, value)
        else:
            merged[key] = value
    return merged


def _load_yaml(config_path: Path) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(path: Optional[str] = None) -> dict:
    """加载配置文件"""
    config_path = Path(path) if path else _DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return {}
    config = _load_yaml(config_path)

    if path is None:
        local_path = config_path.with_suffix(_LOCAL_CONFIG_SUFFIX)
        if local_path.exists():
            config = _merge_config(config, _load_yaml(local_path))

    return config


def get_model_config(config: dict, model: str) -> dict[str, Any]:
    """获取指定模型的配置(api_key, base_url, api_format 等)"""
    models = config.get("llm", {}).get("models", {})
    model_config = dict(models.get(model, {}) or {})
    api_key_env = model_config.get("api_key_env")
    if api_key_env:
        env_value = os.environ.get(str(api_key_env))
        if env_value:
            model_config["api_key"] = env_value
    return model_config


_DEFAULT_TOOLS_CONFIG = {
    "enabled": "all",        # "all" | "readonly" | list[str]
    "bash_timeout": 30,
    "max_output_chars": 10000,
}

_DEFAULT_SECURITY_CONFIG = {
    "enabled": False,
    "approval_timeout_seconds": 300,
    "audit_max_file_bytes": 5 * 1024 * 1024,
}


def get_security_config(config: dict) -> dict[str, Any]:
    """Return validated security defaults without mutating loaded config."""
    raw = (config or {}).get("security") or {}
    merged = dict(_DEFAULT_SECURITY_CONFIG)
    if isinstance(raw, dict):
        merged.update({key: value for key, value in raw.items() if value is not None})
    timeout = merged["approval_timeout_seconds"]
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        raise ValueError("security.approval_timeout_seconds must be positive")
    max_file_bytes = merged["audit_max_file_bytes"]
    if max_file_bytes is not None and (
        isinstance(max_file_bytes, bool)
        or not isinstance(max_file_bytes, int)
        or max_file_bytes <= 0
    ):
        raise ValueError("security.audit_max_file_bytes must be a positive integer or None")
    return merged


def get_tools_config(config: dict) -> dict[str, Any]:
    """获取工具子系统配置,缺省字段填默认值。"""
    raw = (config or {}).get("tools") or {}
    merged = dict(_DEFAULT_TOOLS_CONFIG)
    if isinstance(raw, dict):
        merged.update({k: v for k, v in raw.items() if v is not None})
    return merged


def get_mcp_servers(config: dict) -> list[dict[str, Any]]:
    """Return valid project-declared MCP stdio server definitions."""
    raw = (config or {}).get("mcp", {}).get("servers", [])
    if not isinstance(raw, list):
        raise ValueError("mcp.servers must be a list")
    servers = []
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise ValueError("each MCP server needs a name")
        command = item.get("command")
        if not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
            raise ValueError(f"MCP server {item['name']} needs a command list")
        servers.append({"name": item["name"], "command": command, "enabled": bool(item.get("enabled", False)), "timeout_seconds": item.get("timeout_seconds", 30)})
    return servers
