"""Intent recognition and safe escalation to planning workflows."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class IntentDecision:
    intent: str
    mode: str
    score: int
    reasons: list[str] = field(default_factory=list)


_CODING_TERMS = ("实现", "修改", "添加", "重构", "修复", "排查", "开发", "测试", "代码", "功能", "implement", "refactor", "debug", "fix")
_COMPLEX_TERMS = ("多个", "所有", "整个", "跨", "端到端", "完整", "方案", "架构", "迁移", "并且", "同时", "分步骤", "multi", "across", "end-to-end", "architecture", "migrate")


def classify_intent(text: str, threshold: int = 3) -> IntentDecision:
    """Route only clearly multi-step engineering work into planning mode."""
    normalized = text.casefold().strip()
    if not normalized:
        return IntentDecision("conversation", "react", 0)
    coding = [term for term in _CODING_TERMS if term in normalized]
    complex_terms = [term for term in _COMPLEX_TERMS if term in normalized]
    score = min(2, len(coding)) + min(2, len(complex_terms))
    if len(normalized) >= 80:
        score += 1
    if normalized.count("、") + normalized.count("，") + normalized.count(",") >= 2:
        score += 1
    intent = "coding" if coding else "conversation"
    mode = "plan_execute" if intent == "coding" and score >= threshold else "react"
    return IntentDecision(intent, mode, score, coding + complex_terms)
