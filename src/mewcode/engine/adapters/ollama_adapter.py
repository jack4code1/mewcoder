"""Ollama local model adapter"""

import json
from typing import AsyncIterator, Optional

import httpx

from ..models.client import LLMClient
from ..models.message import LLMResponse, Message, MessageRole, StreamChunk, TokenUsage


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
        """转换消息格式为 Ollama 格式"""
        result = []
        for msg in messages:
            result.append({
                "role": msg.role.value,
                "content": msg.content,
            })
        return result

    async def chat(self, messages: list[Message], **kwargs) -> LLMResponse:
        """发送对话请求（非流式）"""
        payload = {
            "model": self.model,
            "messages": self._convert_messages(messages),
            "stream": False,
            **kwargs,
        }

        response = await self.client.post("/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()

        usage = data.get("usage", {})
        token_usage = TokenUsage(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )

        return LLMResponse(
            content=data.get("message", {}).get("content", ""),
            model=data.get("model", self.model),
            token_usage=token_usage,
            finish_reason="stop" if data.get("done") else "length",
            raw_response=data,
        )

    async def chat_stream(self, messages: list[Message], **kwargs) -> AsyncIterator[StreamChunk]:
        """发送对话请求（流式）"""
        payload = {
            "model": self.model,
            "messages": self._convert_messages(messages),
            "stream": True,
            **kwargs,
        }

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
                        content = data.get("message", {}).get("content", "")
                        done = data.get("done", False)

                        token_usage = None
                        if done:
                            token_usage = TokenUsage(
                                prompt_tokens=data.get("prompt_eval_count", 0),
                                completion_tokens=data.get("eval_count", 0),
                                total_tokens=data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
                            )

                        yield StreamChunk(
                            content=content,
                            model=data.get("model", self.model),
                            finish_reason="stop" if done else None,
                            token_usage=token_usage,
                        )
                    except json.JSONDecodeError:
                        continue

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
