"""Custom API endpoint adapter"""

import json
from typing import AsyncIterator, Optional

import httpx

from ..models.client import LLMClient
from ..models.message import LLMResponse, Message, MessageRole, StreamChunk, TokenUsage


class CustomAdapter(LLMClient):
    """自定义 API 端点适配器"""

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        api_format: str = "openai",
        **kwargs,
    ):
        super().__init__(model, api_key, base_url, **kwargs)
        self.api_format = api_format
        self.base_url = base_url or "http://localhost:8080"

        # 自动检测是否已包含 /v1
        if self.base_url.rstrip("/").endswith("/v1"):
            self.api_prefix = ""
        else:
            self.api_prefix = "/v1"

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self.client = httpx.AsyncClient(
            base_url=self.base_url.rstrip("/"),
            headers=headers,
            timeout=kwargs.get("timeout", 120),
        )

    def _convert_messages(self, messages: list[Message]) -> list[dict]:
        """转换消息格式"""
        result = []
        for msg in messages:
            result.append({
                "role": msg.role.value,
                "content": msg.content,
            })
        return result

    async def chat(self, messages: list[Message], **kwargs) -> LLMResponse:
        """发送对话请求（非流式）"""
        if self.api_format == "openai":
            return await self._chat_openai_format(messages, **kwargs)
        else:
            return await self._chat_generic_format(messages, **kwargs)

    async def _chat_openai_format(self, messages: list[Message], **kwargs) -> LLMResponse:
        """OpenAI 兼容格式请求"""
        payload = {
            "model": self.model,
            "messages": self._convert_messages(messages),
            "stream": False,
            **kwargs,
        }

        response = await self.client.post(f"{self.api_prefix}/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        usage = data.get("usage", {})
        token_usage = TokenUsage(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )

        choice = data["choices"][0]
        message = choice.get("message", {})

        # 优先使用 content，如果没有则使用 reasoning_content
        content = message.get("content", "")
        if not content:
            content = message.get("reasoning_content", "")

        return LLMResponse(
            content=content,
            model=data.get("model", self.model),
            token_usage=token_usage,
            finish_reason=choice.get("finish_reason", "stop"),
            raw_response=data,
        )

    async def _chat_generic_format(self, messages: list[Message], **kwargs) -> LLMResponse:
        """通用格式请求"""
        payload = {
            "model": self.model,
            "prompt": messages[-1].content if messages else "",
            "stream": False,
            **kwargs,
        }

        response = await self.client.post("/generate", json=payload)
        response.raise_for_status()
        data = response.json()

        return LLMResponse(
            content=data.get("response", ""),
            model=self.model,
            token_usage=TokenUsage(),
            finish_reason="stop",
            raw_response=data,
        )

    async def chat_stream(self, messages: list[Message], **kwargs) -> AsyncIterator[StreamChunk]:
        """发送对话请求（流式）"""
        if self.api_format == "openai":
            async for chunk in self._chat_stream_openai_format(messages, **kwargs):
                yield chunk
        else:
            async for chunk in self._chat_stream_generic_format(messages, **kwargs):
                yield chunk

    async def _chat_stream_openai_format(self, messages: list[Message], **kwargs) -> AsyncIterator[StreamChunk]:
        """OpenAI 兼容格式流式请求"""
        payload = {
            "model": self.model,
            "messages": self._convert_messages(messages),
            "stream": True,
            **kwargs,
        }

        async with self.client.stream("POST", f"{self.api_prefix}/chat/completions", json=payload) as response:
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
                            choices = data.get("choices", [])
                            if not choices:
                                continue

                            delta = choices[0].get("delta", {})

                            # 优先使用 content，如果没有则使用 reasoning_content
                            content = delta.get("content", "")
                            if content is None:
                                content = delta.get("reasoning_content", "")
                            if content is None:
                                content = ""

                            finish_reason = choices[0].get("finish_reason")

                            yield StreamChunk(
                                content=content,
                                model=data.get("model", self.model),
                                finish_reason=finish_reason,
                            )
                        except json.JSONDecodeError:
                            continue

    async def _chat_stream_generic_format(self, messages: list[Message], **kwargs) -> AsyncIterator[StreamChunk]:
        """通用格式流式请求"""
        payload = {
            "model": self.model,
            "prompt": messages[-1].content if messages else "",
            "stream": True,
            **kwargs,
        }

        async with self.client.stream("POST", "/generate", json=payload) as response:
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
                        content = data.get("response", "")
                        done = data.get("done", False)

                        yield StreamChunk(
                            content=content,
                            model=self.model,
                            finish_reason="stop" if done else None,
                        )
                    except json.JSONDecodeError:
                        continue

    async def validate_connection(self) -> bool:
        """验证连接是否有效"""
        try:
            response = await self.client.get(f"{self.api_prefix}/models")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()
