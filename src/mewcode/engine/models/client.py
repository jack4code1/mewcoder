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
    async def chat(self, messages: list[Message], **kwargs) -> LLMResponse:
        """
        发送对话请求（非流式）

        Args:
            messages: 消息列表
            **kwargs: 其他参数（temperature, max_tokens 等）

        Returns:
            LLMResponse: 响应对象
        """
        pass

    @abstractmethod
    async def chat_stream(self, messages: list[Message], **kwargs) -> AsyncIterator[StreamChunk]:
        """
        发送对话请求（流式）

        Args:
            messages: 消息列表
            **kwargs: 其他参数

        Yields:
            StreamChunk: 流式响应块
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
