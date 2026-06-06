"""Claude API adapter"""

import json
from typing import AsyncIterator, Optional

import httpx

from ..models.client import LLMClient
from ..models.message import LLMResponse, Message, MessageRole, StreamChunk, TokenUsage


class ClaudeAdapter(LLMClient):
    """Claude API 适配器"""

    DEFAULT_BASE_URL = "https://api.anthropic.com"

    def __init__(self, model: str = "claude-3-5-sonnet-20241022", api_key: Optional[str] = None, base_url: Optional[str] = None, **kwargs):
        super().__init__(model, api_key, base_url, **kwargs)
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            timeout=kwargs.get("timeout", 120),
        )

    def _convert_messages(self, messages: list[Message]) -> tuple[Optional[str], list[dict]]:
        """转换消息格式为 Claude 格式，分离 system 消息"""
        system_prompt = None
        result = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system_prompt = msg.content
            elif msg.role == MessageRole.USER:
                result.append({"role": "user", "content": msg.content})
            elif msg.role == MessageRole.ASSISTANT:
                result.append({"role": "assistant", "content": msg.content})

        return system_prompt, result

    async def chat(self, messages: list[Message], **kwargs) -> LLMResponse:
        """发送对话请求（非流式）"""
        system_prompt, converted_messages = self._convert_messages(messages)

        payload = {
            "model": self.model,
            "messages": converted_messages,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt

        response = await self.client.post("/v1/messages", json=payload)
        response.raise_for_status()
        data = response.json()

        usage = data.get("usage", {})
        token_usage = TokenUsage(
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
            total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        )

        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")

        return LLMResponse(
            content=content,
            model=data.get("model", self.model),
            token_usage=token_usage,
            finish_reason=data.get("stop_reason", "stop"),
            raw_response=data,
        )

    async def chat_stream(self, messages: list[Message], **kwargs) -> AsyncIterator[StreamChunk]:
        """发送对话请求（流式）"""
        system_prompt, converted_messages = self._convert_messages(messages)

        payload = {
            "model": self.model,
            "messages": converted_messages,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "stream": True,
        }
        if system_prompt:
            payload["system"] = system_prompt

        async with self.client.stream("POST", "/v1/messages", json=payload) as response:
            response.raise_for_status()
            buffer = ""

            async for chunk in response.aiter_bytes():
                buffer += chunk.decode("utf-8")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue

                    if line.startswith("event: "):
                        event_type = line[7:]
                        continue

                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            event_type = data.get("type", "")

                            if event_type == "content_block_delta":
                                delta = data.get("delta", {})
                                content = delta.get("text", "")
                                yield StreamChunk(
                                    content=content,
                                    model=self.model,
                                )
                            elif event_type == "message_delta":
                                stop_reason = data.get("delta", {}).get("stop_reason")
                                usage = data.get("usage", {})
                                token_usage = TokenUsage(
                                    prompt_tokens=0,
                                    completion_tokens=usage.get("output_tokens", 0),
                                    total_tokens=usage.get("output_tokens", 0),
                                )
                                yield StreamChunk(
                                    content="",
                                    model=self.model,
                                    finish_reason=stop_reason,
                                    token_usage=token_usage,
                                )
                            elif event_type == "message_start":
                                message = data.get("message", {})
                                usage = message.get("usage", {})
                                token_usage = TokenUsage(
                                    prompt_tokens=usage.get("input_tokens", 0),
                                    completion_tokens=0,
                                    total_tokens=usage.get("input_tokens", 0),
                                )
                                yield StreamChunk(
                                    content="",
                                    model=message.get("model", self.model),
                                    token_usage=token_usage,
                                )
                        except json.JSONDecodeError:
                            continue

    async def validate_connection(self) -> bool:
        """验证连接是否有效"""
        try:
            response = await self.client.get("/v1/models")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()
