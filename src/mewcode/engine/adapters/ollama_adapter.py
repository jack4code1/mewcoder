"""Ollama local model adapter"""

import json
from typing import AsyncIterator, Optional

import httpx

from ..models.client import LLMClient
from ..models.message import LLMResponse, Message, MessageRole, StreamChunk, ToolCall, TokenUsage
from ._openai_protocol import OpenAIToolCallAggregator, convert_messages_to_openai


class OllamaAdapter(LLMClient):
    """Ollama 本地模型适配器"""

    DEFAULT_BASE_URL = "http://localhost:11434"

    def __init__(self, model: str = "llama2", api_key: Optional[str] = None, base_url: Optional[str] = None, **kwargs):
        super().__init__(model, api_key, base_url, **kwargs)
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=kwargs.get("timeout", 300),
        )

    def _convert_messages(self, messages: list[Message]) -> list[dict]:
        """转换消息格式为 Ollama 格式 — 与 OpenAI 兼容,含 tool_calls / role:tool"""
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

        response = await self.client.post("/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()

        usage = data.get("usage", {})
        token_usage = TokenUsage(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )

        msg = data.get("message", {}) or {}
        # Ollama follows the OpenAI tool_calls shape on /api/chat for
        # tool-aware models.
        tool_calls: Optional[list[ToolCall]] = None
        raw_tcs = msg.get("tool_calls")
        if raw_tcs:
            agg = OpenAIToolCallAggregator()
            for i, tc in enumerate(raw_tcs):
                fn = tc.get("function", {})
                args = fn.get("arguments", "")
                # Ollama may already give a dict for arguments; the
                # aggregator only accepts strings.
                if isinstance(args, dict):
                    args_str = json.dumps(args)
                else:
                    args_str = args or ""
                agg.feed([
                    {
                        "index": tc.get("index", i),
                        "id": tc.get("id", f"call_{i}"),
                        "function": {
                            "name": fn.get("name", ""),
                            "arguments": args_str,
                        },
                    }
                ])
            tool_calls = agg.finalize()

        return LLMResponse(
            content=msg.get("content", "") or "",
            model=data.get("model", self.model),
            token_usage=token_usage,
            finish_reason="stop" if data.get("done") else "length",
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

        agg = OpenAIToolCallAggregator()

        async with self.client.stream("POST", "/api/chat", json=payload) as response:
            response.raise_for_status()
            buffer = ""

            async for chunk in response.aiter_bytes():
                buffer += chunk.decode("utf-8")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                        msg = data.get("message", {}) or {}
                        content = msg.get("content", "") or ""
                        done = data.get("done", False)

                        tc_deltas = msg.get("tool_calls")
                        if tc_deltas:
                            # Ollama may emit each call whole; normalise
                            # arguments to string form for the aggregator.
                            normalised = []
                            for i, tc in enumerate(tc_deltas):
                                fn = tc.get("function", {}) or {}
                                args = fn.get("arguments", "")
                                if isinstance(args, dict):
                                    args = json.dumps(args)
                                normalised.append(
                                    {
                                        "index": tc.get("index", i),
                                        "id": tc.get("id", f"call_{i}"),
                                        "function": {
                                            "name": fn.get("name", ""),
                                            "arguments": args or "",
                                        },
                                    }
                                )
                            agg.feed(normalised)

                        token_usage = None
                        if done:
                            token_usage = TokenUsage(
                                prompt_tokens=data.get("prompt_eval_count", 0),
                                completion_tokens=data.get("eval_count", 0),
                                total_tokens=data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
                            )

                        if content or not done:
                            yield StreamChunk(
                                content=content,
                                model=data.get("model", self.model),
                                finish_reason="stop" if done else None,
                                token_usage=token_usage,
                            )

                        if done and agg.has_calls():
                            yield StreamChunk(
                                content="",
                                model=data.get("model", self.model),
                                finish_reason="tool_calls",
                                token_usage=token_usage,
                                tool_calls=agg.finalize(),
                            )
                            agg = OpenAIToolCallAggregator()
                        elif done:
                            yield StreamChunk(
                                content="",
                                model=data.get("model", self.model),
                                finish_reason="stop",
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
            response = await self.client.get("/api/tags")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()
