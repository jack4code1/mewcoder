"""Adapter factory for creating LLM clients"""

from typing import Optional

from ..models.client import LLMClient
from .claude_adapter import ClaudeAdapter
from .custom_adapter import CustomAdapter
from .ollama_adapter import OllamaAdapter
from .openai_adapter import OpenAIAdapter


class AdapterFactory:
    """适配器工厂，用于创建和管理 LLM 客户端"""

    # 支持的提供商及其默认模型
    PROVIDERS = {
        "openai": {
            "adapter": OpenAIAdapter,
            "default_model": "gpt-4",
            "models": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo", "gpt-4o", "gpt-4o-mini"],
        },
        "claude": {
            "adapter": ClaudeAdapter,
            "default_model": "claude-3-5-sonnet-20241022",
            "models": [
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307",
            ],
        },
        "ollama": {
            "adapter": OllamaAdapter,
            "default_model": "llama2",
            "models": [],  # 动态获取
        },
        "custom": {
            "adapter": CustomAdapter,
            "default_model": "default",
            "models": [],
        },
    }

    @classmethod
    def detect_provider(cls, model: str) -> str:
        """根据模型名称自动检测提供商"""
        model_lower = model.lower()

        if model_lower.startswith("gpt-") or model_lower.startswith("gpt_"):
            return "openai"
        elif model_lower.startswith("claude"):
            return "claude"
        elif model_lower in ["llama2", "llama3", "mistral", "codellama", "phi", "gemma"]:
            return "ollama"
        else:
            # 尝试匹配已知模型
            for provider, config in cls.PROVIDERS.items():
                if model in config["models"]:
                    return provider

            # 默认使用自定义适配器
            return "custom"

    @classmethod
    def create_client(
        cls,
        model: str,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs,
    ) -> LLMClient:
        """
        创建 LLM 客户端

        Args:
            model: 模型名称
            provider: 提供商名称（可选，自动检测）
            api_key: API 密钥
            base_url: API 基础 URL
            **kwargs: 其他配置参数

        Returns:
            LLMClient: LLM 客户端实例
        """
        if provider is None:
            provider = cls.detect_provider(model)

        if provider not in cls.PROVIDERS:
            raise ValueError(f"不支持的提供商: {provider}")

        adapter_class = cls.PROVIDERS[provider]["adapter"]

        # 根据提供商设置默认值
        if provider == "openai":
            return adapter_class(
                model=model,
                api_key=api_key,
                base_url=base_url or "https://api.openai.com/v1",
                **kwargs,
            )
        elif provider == "claude":
            return adapter_class(
                model=model,
                api_key=api_key,
                base_url=base_url or "https://api.anthropic.com",
                **kwargs,
            )
        elif provider == "ollama":
            return adapter_class(
                model=model,
                base_url=base_url or "http://localhost:11434",
                **kwargs,
            )
        else:
            return adapter_class(
                model=model,
                api_key=api_key,
                base_url=base_url,
                api_format=kwargs.pop("api_format", "openai"),
                **kwargs,
            )

    @classmethod
    def list_providers(cls) -> list[str]:
        """列出所有支持的提供商"""
        return list(cls.PROVIDERS.keys())

    @classmethod
    def list_models(cls, provider: str) -> list[str]:
        """列出指定提供商的可用模型"""
        if provider not in cls.PROVIDERS:
            return []
        return cls.PROVIDERS[provider]["models"]
