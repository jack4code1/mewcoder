"""Claude API adapter"""

import json
from typing import AsyncIterator, Optional

import httpx

from ..models.client import LLMClient
from ..models.message import LLMResponse, Message, MessageRole, StreamChunk, ToolCall, TokenUsage


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

    def _convert_messages(
        self, messages: list[Message]
    ) -> tuple[Optional[str], list[dict]]:
        """转换消息格式为 Claude (Anthropic) 形态。

        要点:
          - SYSTEM 消息抽出为 top-level system 字段。
          - ASSISTANT.tool_calls -> content blocks 数组,含 text 与 tool_use。
          - 连续 TOOL 消息聚合为一条 user 消息,内含若干 tool_result 块。
        """
        system_prompt: Optional[str] = None
        result: list[dict] = []
        i = 0
        while i < len(messages):
            msg = messages[i]
            if msg.role == MessageRole.SYSTEM:
                # 多个 SYSTEM 取最后一个(通常每次只注入一次)
                system_prompt = msg.content
                i += 1
                continue

            if msg.role == MessageRole.USER:
                if msg.content:
                    result.append({
                        "role": "user",
                        "content": [{"type": "text", "text": msg.content}],
                    })
                i += 1
                continue

            if msg.role == MessageRole.ASSISTANT:
                blocks: list[dict] = []
                if msg.content:
                    blocks.append({"type": "text", "text": msg.content})
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        blocks.append({
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.input or {},
                        })
                if not blocks:
                    blocks.append({"type": "text", "text": ""})
                result.append({"role": "assistant", "content": blocks})
                i += 1
                continue

            if msg.role == MessageRole.TOOL:
                # Aggregate consecutive TOOL messages into a single user
                # message containing one tool_result block per call.
                tool_blocks: list[dict] = []
                while i < len(messages) and messages[i].role == MessageRole.TOOL:
                    tmsg = messages[i]
                    block: dict = {
                        "type": "tool_result",
                        "tool_use_id": tmsg.tool_call_id or "",
                        "content": tmsg.content or "",
                    }
                    if tmsg.tool_result_is_error:
                        block["is_error"] = True
                    tool_blocks.append(block)
                    i += 1
                result.append({"role": "user", "content": tool_blocks})
                continue

            # Unknown role: skip defensively.
            i += 1

        return system_prompt, result

    async def chat(
        self,
        messages: list[Message],
        tools: Optional[list[dict]] = None,
        **kwargs,
    ) -> LLMResponse:
        """发送对话请求(非流式)"""
        system_prompt, converted_messages = self._convert_messages(messages)

        payload = {
            "model": self.model,
            "messages": converted_messages,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if tools:
            payload["tools"] = tools

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
        tool_calls: list[ToolCall] = []
        for block in data.get("content", []):
            btype = block.get("type")
            if btype == "text":
                content += block.get("text", "")
            elif btype == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.get("id", ""),
                        name=block.get("name", ""),
                        input=block.get("input") or {},
                    )
                )

        return LLMResponse(
            content=content,
            model=data.get("model", self.model),
            token_usage=token_usage,
            finish_reason=data.get("stop_reason", "stop"),
            raw_response=data,
            tool_calls=tool_calls or None,
        )

    async def chat_stream(
        self,
        messages: list[Message],
        tools: Optional[list[dict]] = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """发送对话请求(流式)"""
        system_prompt, converted_messages = self._convert_messages(messages)

        payload = {
            "model": self.model,
            "messages": converted_messages,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "stream": True,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if tools:
            payload["tools"] = tools

        # block_buf[index] = {"type": "tool_use", "id": ..., "name": ...,
        #                     "partial_json": "..."} for tool_use blocks.
        block_buf: dict[int, dict] = {}
        completed_tool_calls: list[ToolCall] = []
        last_output_tokens = 0

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
                        # Event-line is informational; the data line carries
                        # the full type. We rely on the JSON `type` field.
                        continue

                    if not line.startswith("data: "):
                        continue

                    try:
                        data = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue

                    event_type = data.get("type", "")

                    if event_type == "message_start":
                        message = data.get("message", {})
                        usage = message.get("usage", {})
                        if "input_tokens" in usage:
                            input_tokens = int(usage.get("input_tokens", 0) or 0)
                            token_usage = TokenUsage(
                                prompt_tokens=input_tokens,
                                completion_tokens=0,
                                total_tokens=input_tokens,
                            )
                            yield StreamChunk(
                                content="",
                                model=message.get("model", self.model),
                                token_usage=token_usage,
                            )

                    elif event_type == "content_block_start":
                        idx = data.get("index", 0)
                        block = data.get("content_block", {}) or {}
                        if block.get("type") == "tool_use":
                            block_buf[idx] = {
                                "type": "tool_use",
                                "id": block.get("id", ""),
                                "name": block.get("name", ""),
                                "partial_json": "",
                            }

                    elif event_type == "content_block_delta":
                        idx = data.get("index", 0)
                        delta = data.get("delta", {}) or {}
                        dtype = delta.get("type", "")
                        if dtype == "text_delta":
                            text = delta.get("text", "") or ""
                            if text:
                                yield StreamChunk(
                                    content=text,
                                    model=self.model,
                                )
                        elif dtype == "input_json_delta":
                            if idx in block_buf:
                                block_buf[idx]["partial_json"] += delta.get("partial_json", "") or ""

                    elif event_type == "content_block_stop":
                        idx = data.get("index", 0)
                        slot = block_buf.pop(idx, None)
                        if slot and slot.get("type") == "tool_use":
                            args_str = slot.get("partial_json", "") or ""
                            parse_error: Optional[str] = None
                            parsed: dict = {}
                            if args_str.strip():
                                try:
                                    loaded = json.loads(args_str)
                                    if isinstance(loaded, dict):
                                        parsed = loaded
                                    else:
                                        parse_error = (
                                            f"tool input must be a JSON object, got {type(loaded).__name__}"
                                        )
                                except json.JSONDecodeError as e:
                                    parse_error = f"failed to parse tool input JSON: {e.msg}"
                            completed_tool_calls.append(
                                ToolCall(
                                    id=slot.get("id", "") or f"tool_use_{idx}",
                                    name=slot.get("name", "") or "",
                                    input=parsed,
                                    parse_error=parse_error,
                                )
                            )

                    elif event_type == "message_delta":
                        stop_reason = data.get("delta", {}).get("stop_reason")
                        usage = data.get("usage", {})
                        token_usage = None
                        if "output_tokens" in usage:
                            output_tokens = int(usage.get("output_tokens", 0) or 0)
                            output_delta = max(0, output_tokens - last_output_tokens)
                            last_output_tokens = max(last_output_tokens, output_tokens)
                            token_usage = TokenUsage(
                                prompt_tokens=0,
                                completion_tokens=output_delta,
                                total_tokens=output_delta,
                            )
                        # Defer emitting tool_calls until message_stop so the
                        # consumer sees a single terminal chunk.
                        if completed_tool_calls and stop_reason == "tool_use":
                            yield StreamChunk(
                                content="",
                                model=self.model,
                                finish_reason=stop_reason,
                                token_usage=token_usage,
                                tool_calls=list(completed_tool_calls),
                            )
                            completed_tool_calls = []
                        else:
                            yield StreamChunk(
                                content="",
                                model=self.model,
                                finish_reason=stop_reason,
                                token_usage=token_usage,
                            )

                    elif event_type == "message_stop":
                        # Already surfaced via message_delta. If the server
                        # somehow skipped message_delta and tool calls remain,
                        # surface them now.
                        if completed_tool_calls:
                            yield StreamChunk(
                                content="",
                                model=self.model,
                                finish_reason="tool_use",
                                tool_calls=list(completed_tool_calls),
                            )
                            completed_tool_calls = []

        # Final safety net for tool_calls that never got flushed.
        if completed_tool_calls:
            yield StreamChunk(
                content="",
                model=self.model,
                finish_reason="tool_use",
                tool_calls=list(completed_tool_calls),
            )

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
