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
    """获取指定模型的配置（api_key, base_url, api_format 等）"""
    models = config.get("llm", {}).get("models", {})
    return models.get(model, {})
