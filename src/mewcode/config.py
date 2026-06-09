"""Configuration loader for MewCode"""

from pathlib import Path
from typing import Any, Optional

import yaml


_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"


def load_config(path: Optional[str] = None) -> dict:
    """加载配置文件"""
    config_path = Path(path) if path else _DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_model_config(config: dict, model: str) -> dict[str, Any]:
    """获取指定模型的配置(api_key, base_url, api_format 等)"""
    models = config.get("llm", {}).get("models", {})
    return models.get(model, {})


_DEFAULT_TOOLS_CONFIG = {
    "enabled": "all",        # "all" | "readonly" | list[str]
    "bash_timeout": 30,
    "max_output_chars": 10000,
}


def get_tools_config(config: dict) -> dict[str, Any]:
    """获取工具子系统配置,缺省字段填默认值。"""
    raw = (config or {}).get("tools") or {}
    merged = dict(_DEFAULT_TOOLS_CONFIG)
    if isinstance(raw, dict):
        merged.update({k: v for k, v in raw.items() if v is not None})
    return merged
