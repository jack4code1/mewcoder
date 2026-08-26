"""Structured intent routing for direct, ReAct, planning, and delegation flows."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Awaitable, Callable, Protocol


@dataclass(frozen=True)
class IntentDecision:
    intent: str
    mode: str
    requires_tools: bool
    requires_code_changes: bool
    execution_chain_length: int
    decision_chain_length: int
    suggested_roles: tuple[str, ...] = ()
    complexity_factors: dict[str, bool] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)

    @property
    def score(self) -> int:
        return self.execution_chain_length + self.decision_chain_length


_VALID_ROUTES = {"direct", "react", "plan_execute", "delegate"}
_VALID_COMPLEXITIES = {"low", "medium", "high"}
_COMPLEXITY_FACTORS = (
    "tool_calls", "multiple_files", "code_changes", "multiple_stages",
    "test_validation", "cross_role_collaboration",
)


class ChatClient(Protocol):
    async def chat(self, messages, tools=None, **kwargs): ...


@dataclass
class ExecutionSignals:
    """Observed work used to re-route a running ReAct task."""

    turns: int = 0
    tool_calls: int = 0
    read_search_calls: int = 0
    write_calls: int = 0
    failures: int = 0


_TOOL_TERMS = ("读取", "查看", "分析项目", "搜索", "运行", "检查", "测试", "目录", "文件", "read", "inspect", "search", "run", "test", "repository")
_CODE_TERMS = ("实现", "修改", "添加", "重构", "修复", "排查", "开发", "代码", "功能", "implement", "modify", "add", "refactor", "debug", "fix")
_MULTI_STEP_TERMS = ("多个文件", "跨文件", "端到端", "完整", "迁移", "重构", "并且", "同时", "分步骤", "multi-file", "across", "end-to-end", "migrate")
_DECISION_TERMS = ("方案", "架构", "权衡", "设计", "排查", "兼容", "性能", "安全", "验收", "architecture", "tradeoff", "design", "compatibility", "performance", "security")


def _matches(text: str, terms: tuple[str, ...]) -> list[str]:
    return [term for term in terms if term in text]


def classify_intent(text: str, threshold: int = 3) -> IntentDecision:
    """Route according to the execution and decision chain implied by a task."""
    normalized = text.casefold().strip()
    if not normalized:
        return IntentDecision("conversation", "direct", False, False, 0, 0)

    tool_hits = _matches(normalized, _TOOL_TERMS)
    code_hits = _matches(normalized, _CODE_TERMS)
    multi_hits = _matches(normalized, _MULTI_STEP_TERMS)
    decision_hits = _matches(normalized, _DECISION_TERMS)
    requires_tools = bool(tool_hits or code_hits)
    requires_code_changes = bool(code_hits)

    execution_chain = int(requires_tools) + int(requires_code_changes)
    if multi_hits:
        execution_chain += 2
    if "测试" in normalized or "test" in normalized:
        execution_chain += 1
    decision_chain = min(3, len(decision_hits) + int(requires_code_changes and ("测试" in normalized or "test" in normalized)))

    intent = "coding" if requires_code_changes else "tool_use" if requires_tools else "conversation"
    if not requires_tools:
        mode = "direct"
    elif execution_chain >= 5 or decision_chain >= 3:
        mode = "delegate"
    elif execution_chain + decision_chain >= threshold:
        mode = "plan_execute"
    else:
        mode = "react"
    roles = ("researcher", "implementer", "reviewer") if mode == "delegate" else ()
    return IntentDecision(
        intent, mode, requires_tools, requires_code_changes, execution_chain,
        decision_chain, roles,
        {
            "tool_calls": requires_tools,
            "multiple_files": bool(multi_hits),
            "code_changes": requires_code_changes,
            "multiple_stages": bool(multi_hits),
            "test_validation": "测试" in normalized or "test" in normalized,
            "cross_role_collaboration": mode == "delegate",
        },
        tool_hits + code_hits + multi_hits + decision_hits,
    )


def escalation_target(signals: ExecutionSignals) -> str | None:
    """Upgrade only after observed work proves the initial route was too small."""
    if signals.turns >= 3 and signals.read_search_calls >= 4 and signals.write_calls >= 2:
        return "delegate"
    if signals.tool_calls >= 6 or (signals.turns >= 2 and signals.read_search_calls >= 3 and signals.write_calls >= 1):
        return "plan_execute"
    if signals.failures >= 2 and signals.tool_calls >= 3:
        return "plan_execute"
    return None


def parse_route_result(raw: str) -> IntentDecision:
    """Parse and validate an LLM route response before any workflow runs."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("route result must be a JSON object")
    route = data.get("route")
    complexity = data.get("complexity")
    intent = data.get("intent")
    requires_tools = data.get("requires_tools")
    requires_code_changes = data.get("requires_code_changes")
    if not isinstance(complexity, dict):
        raise ValueError("complexity must be an object")
    level = complexity.get("level")
    factors = {key: complexity.get(key) for key in _COMPLEXITY_FACTORS}
    if route not in _VALID_ROUTES or level not in _VALID_COMPLEXITIES or not isinstance(intent, str):
        raise ValueError("route result has invalid intent, complexity, or route")
    if not all(isinstance(value, bool) for value in factors.values()):
        raise ValueError("complexity factors must be booleans")
    if not isinstance(requires_tools, bool) or not isinstance(requires_code_changes, bool):
        raise ValueError("route result requires boolean capability flags")
    if route == "direct" and requires_tools:
        raise ValueError("direct route cannot require tools")
    if route in {"react", "plan_execute", "delegate"} and not requires_tools:
        raise ValueError("agent routes must require tools")
    if route in {"plan_execute", "delegate"} and level == "low":
        raise ValueError("complex workflows cannot be low complexity")
    levels = {"low": 0, "medium": 1, "high": 3}
    roles = tuple(data.get("suggested_roles", []))
    if not all(isinstance(role, str) for role in roles):
        raise ValueError("suggested_roles must be strings")
    reasons = data.get("reasons", [])
    if not isinstance(reasons, list) or not all(isinstance(item, str) for item in reasons):
        raise ValueError("reasons must be a string list")
    return IntentDecision(
        intent=intent,
        mode=route,
        requires_tools=requires_tools,
        requires_code_changes=requires_code_changes,
        execution_chain_length=levels[level] + sum(factors[key] for key in ("tool_calls", "multiple_files", "code_changes", "multiple_stages", "test_validation")),
        decision_chain_length=levels[level] + int(factors["cross_role_collaboration"]),
        suggested_roles=roles,
        complexity_factors=factors,
        reasons=reasons,
    )


class LLMRouter:
    """Use an LLM for semantic routing, with deterministic validation and fallback."""

    async def route(self, client: ChatClient, text: str, threshold: int = 3) -> IntentDecision:
        try:
            from ..models.message import Message, MessageRole

            response = await client.chat([
                Message(MessageRole.SYSTEM, "You are a task router. Return only JSON with intent, route (direct|react|plan_execute|delegate), requires_tools, requires_code_changes, suggested_roles, reasons, and complexity. complexity must be an object with level (low|medium|high) plus boolean tool_calls, multiple_files, code_changes, multiple_stages, test_validation, cross_role_collaboration. Judge complexity from these six dimensions: local tool use, multiple files, code changes, multiple execution phases, test/verification, and cross-role collaboration. Choose direct for no-tool questions; react for one bounded tool task; plan_execute for multi-step work; delegate for high-decision specialist collaboration."),
                Message(MessageRole.USER, text),
            ])
            return parse_route_result(response.content)
        except Exception:
            return classify_intent(text, threshold)
