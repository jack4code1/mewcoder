"""Data models for MewCode engine"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class MessageRole(Enum):
    """消息角色枚举"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class TokenUsage:
    """Token 用量统计"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


@dataclass
class Message:
    """对话消息"""
    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    token_usage: Optional[TokenUsage] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转换为字典格式"""
        result = {
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        """从字典创建消息"""
        return cls(
            role=MessageRole(data["role"]),
            content=data["content"],
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat())),
            metadata=data.get("metadata", {}),
        )


@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str
    model: str
    token_usage: TokenUsage
    finish_reason: str = "stop"
    raw_response: dict = field(default_factory=dict)


@dataclass
class StreamChunk:
    """流式响应块"""
    content: str
    model: str
    finish_reason: Optional[str] = None
    token_usage: Optional[TokenUsage] = None
