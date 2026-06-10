"""OpenAI API adapter"""

import json
from typing import AsyncIterator, Optional

import httpx

from ..models.client import LLMClient
from ..models.message import LLMResponse, Message, MessageRole, StreamChunk, ToolCall, TokenUsage
from ._openai_protocol import (
    OpenAIToolCallAggregator,
    add_stream_usage_option,
    convert_messages_to_openai,
    token_usage_from_openai_usage,
)


class OpenAIAdapter(LLMClient):
    """OpenAI API 适配器"""

    DEFAULT_BASE_URL = "https://api.openai.com/v1"

    def __init__(self, model: str = "gpt-4", api_key: Optional[str] = None, base_url: Optional[str] = None, **kwargs):
        super().__init__(model, api_key, base_url, **kwargs)
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=kwargs.get("timeout", 120),
        )

    def _convert_messages(self, messages: list[Message]) -> list[dict]:
        """转换消息格式为 OpenAI 格式 — 含 tool_calls / role:tool 支持"""
        return convert_messages_to_openai(messages)

    async def chat(
        self,
        messages: list[Message],
        tools: Optional[list[dict]] = None,
        **kwargs,
    ) -> LLMResponse:
        """发送对话请求(非流式)"""
        payload = {
            "model": self.model,
            "messages": self._convert_messages(messages),
            "stream": False,
            **kwargs,
        }
        if tools:
            payload["tools"] = tools

        response = await self.client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        usage = data.get("usage", {})
        token_usage = token_usage_from_openai_usage(usage)

        choice = data["choices"][0]
        message = choice.get("message", {})

        tool_calls: Optional[list[ToolCall]] = None
        raw_tcs = message.get("tool_calls")
        if raw_tcs:
            agg = OpenAIToolCallAggregator()
            for i, tc in enumerate(raw_tcs):
                fn = tc.get("function", {})
                agg.feed([
                    {
                        "index": tc.get("index", i),
                        "id": tc.get("id", ""),
                        "function": {
                            "name": fn.get("name", ""),
                            "arguments": fn.get("arguments", ""),
                        },
                    }
                ])
            tool_calls = agg.finalize()

        return LLMResponse(
            content=message.get("content", "") or "",
            model=data.get("model", self.model),
            token_usage=token_usage,
            finish_reason=choice.get("finish_reason", "stop"),
            raw_response=data,
            tool_calls=tool_calls,
        )

    async def chat_stream(
        self,
        messages: list[Message],
        tools: Optional[list[dict]] = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """发送对话请求(流式)"""
        payload = {
            "model": self.model,
            "messages": self._convert_messages(messages),
            "stream": True,
            **kwargs,
        }
        if tools:
            payload["tools"] = tools
        add_stream_usage_option(payload)

        agg = OpenAIToolCallAggregator()

        async with self.client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()
            buffer = ""

            async for chunk in response.aiter_bytes():
                buffer += chunk.decode("utf-8")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            choices = data.get("choices") or []
                            token_usage = None
                            if data.get("usage") is not None:
                                token_usage = token_usage_from_openai_usage(data["usage"])

                            if not choices:
                                if token_usage is not None:
                                    yield StreamChunk(
                                        content="",
                                        model=data.get("model", self.model),
                                        token_usage=token_usage,
                                    )
                                continue

                            choice = choices[0]
                            delta = choice.get("delta", {})

                            tc_deltas = delta.get("tool_calls")
                            if tc_deltas:
                                agg.feed(tc_deltas)

                            content = delta.get("content", "") or ""
                            finish_reason = choice.get("finish_reason")

                            if content or finish_reason is None:
                                yield StreamChunk(
                                    content=content,
                                    model=data.get("model", self.model),
                                    finish_reason=finish_reason,
                                )

                            if finish_reason and agg.has_calls():
                                yield StreamChunk(
                                    content="",
                                    model=data.get("model", self.model),
                                    finish_reason=finish_reason,
                                    token_usage=token_usage,
                                    tool_calls=agg.finalize(),
                                )
                                agg = OpenAIToolCallAggregator()
                            elif finish_reason:
                                yield StreamChunk(
                                    content="",
                                    model=data.get("model", self.model),
                                    finish_reason=finish_reason,
                                    token_usage=token_usage,
                                )
                        except json.JSONDecodeError:
                            continue

        if agg.has_calls():
            yield StreamChunk(
                content="",
                model=self.model,
                finish_reason="tool_calls",
                tool_calls=agg.finalize(),
            )

    async def validate_connection(self) -> bool:
        """验证连接是否有效"""
        try:
            response = await self.client.get("/models")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()
