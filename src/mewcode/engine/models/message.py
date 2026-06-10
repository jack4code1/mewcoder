"""Data models for MewCode engine.

Tool-calling support (chapter 02-tools):

  - ToolCall                       — protocol-neutral form of a model-issued
                                     tool invocation.
  - Message.tool_calls             — set on assistant messages that request
                                     tools.
  - Message.tool_call_id           — set on TOOL-role messages that carry the
                                     execution result for a particular call.
  - Message.tool_result_is_error   — set on TOOL-role messages to flag a
                                     recoverable error result.
  - StreamChunk.tool_calls         — adapters yield a final stream chunk that
                                     carries the aggregated tool calls when
                                     the model requests tools.

All new fields are optional. to_dict / from_dict are backward-compatible:
old session YAML files (without these fields) load with the new fields
defaulting to None.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


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

    def to_dict(self) -> dict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "TokenUsage":
        data = data or {}
        return cls(
            prompt_tokens=int(data.get("prompt_tokens", 0) or 0),
            completion_tokens=int(data.get("completion_tokens", 0) or 0),
            total_tokens=int(data.get("total_tokens", 0) or 0),
        )


@dataclass
class ToolCall:
    """A single tool invocation requested by the model.

    Stored in a protocol-neutral, OpenAI-flavoured form. Adapters translate
    to the wire format on send (e.g. Anthropic content blocks).

    Attributes:
        id: Stable identifier issued by the model (OpenAI: tool_calls[*].id;
            Anthropic: tool_use block id).
        name: Tool name.
        input: Parsed arguments. dict — never the raw JSON string. Adapters
            re-serialize when emitting OpenAI's `arguments` field.
        parse_error: Set when streaming aggregation could not parse the
            argument JSON. Adapters / dispatchers turn this into an
            isError ToolResult so the model gets feedback.
    """

    id: str
    name: str
    input: dict[str, Any] = field(default_factory=dict)
    parse_error: Optional[str] = None

    def to_dict(self) -> dict:
        out: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "input": self.input,
        }
        if self.parse_error:
            out["parse_error"] = self.parse_error
        return out

    @classmethod
    def from_dict(cls, data: dict) -> "ToolCall":
        return cls(
            id=data["id"],
            name=data["name"],
            input=data.get("input", {}) or {},
            parse_error=data.get("parse_error"),
        )


@dataclass
class Message:
    """对话消息"""
    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    token_usage: Optional[TokenUsage] = None
    metadata: dict = field(default_factory=dict)

    # ----- Tool-calling extensions (chapter 02-tools) -----
    # All optional; absent on plain text messages so old sessions keep working.
    tool_calls: Optional[list[ToolCall]] = None
    tool_call_id: Optional[str] = None
    tool_result_is_error: Optional[bool] = None

    def to_dict(self) -> dict:
        """转换为字典格式"""
        result: dict[str, Any] = {
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.metadata:
            result["metadata"] = self.metadata
        if self.token_usage is not None:
            result["token_usage"] = self.token_usage.to_dict()
        if self.tool_calls:
            result["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]
        if self.tool_call_id is not None:
            result["tool_call_id"] = self.tool_call_id
        if self.tool_result_is_error is not None:
            result["tool_result_is_error"] = self.tool_result_is_error
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        """从字典创建消息"""
        raw_tool_calls = data.get("tool_calls")
        tool_calls = (
            [ToolCall.from_dict(tc) for tc in raw_tool_calls]
            if raw_tool_calls
            else None
        )
        return cls(
            role=MessageRole(data["role"]),
            content=data.get("content", "") or "",
            timestamp=datetime.fromisoformat(
                data.get("timestamp", datetime.now().isoformat())
            ),
            token_usage=(
                TokenUsage.from_dict(data.get("token_usage"))
                if data.get("token_usage") is not None
                else None
            ),
            metadata=data.get("metadata", {}) or {},
            tool_calls=tool_calls,
            tool_call_id=data.get("tool_call_id"),
            tool_result_is_error=data.get("tool_result_is_error"),
        )


@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str
    model: str
    token_usage: TokenUsage
    finish_reason: str = "stop"
    raw_response: dict = field(default_factory=dict)
    tool_calls: Optional[list[ToolCall]] = None


@dataclass
class StreamChunk:
    """流式响应块"""
    content: str
    model: str
    finish_reason: Optional[str] = None
    token_usage: Optional[TokenUsage] = None
    # Tool-calling: adapters emit a final StreamChunk with tool_calls populated
    # once the model finishes requesting tools. None on every other chunk.
    tool_calls: Optional[list[ToolCall]] = None
