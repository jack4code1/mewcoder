"""LLM Client abstract base class"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional

from .message import LLMResponse, Message, StreamChunk


class LLMClient(ABC):
    """LLM 客户端抽象基类"""

    def __init__(self, model: str, api_key: Optional[str] = None, base_url: Optional[str] = None, **kwargs):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.config = kwargs

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: Optional[list[dict]] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        发送对话请求(非流式)

        Args:
            messages: 消息列表
            tools: 可选,已经按目标协议格式化好的工具描述列表
                   (调用方应使用 ToolRegistry.to_openai_format() 或
                    to_anthropic_format() 准备)。当为 None 或空列表时,
                    适配器不向 API 发送 tools 参数。
            **kwargs: 其他参数(temperature, max_tokens 等)

        Returns:
            LLMResponse: 响应对象
        """
        pass

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[Message],
        tools: Optional[list[dict]] = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """
        发送对话请求(流式)

        Args:
            messages: 消息列表
            tools: 可选,已经按目标协议格式化好的工具描述列表(同 chat)
            **kwargs: 其他参数

        Yields:
            StreamChunk: 流式响应块。当模型请求工具时,适配器在最后
                        emit 一个携带 tool_calls 的 StreamChunk。
        """
        pass

    @abstractmethod
    async def validate_connection(self) -> bool:
        """
        验证连接是否有效

        Returns:
            bool: 连接是否有效
        """
        pass

    def get_model_name(self) -> str:
        """获取模型名称"""
        return self.model
