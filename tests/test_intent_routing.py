import pytest

from mewcode.engine.orchestration import (
    ExecutionSignals,
    RouteDispatcher,
    classify_intent,
    escalation_target,
    parse_route_result,
)


def test_simple_tool_request_uses_react_mode():
    decision = classify_intent("读取 config.yaml 并告诉我默认模型")

    assert decision.intent == "tool_use"
    assert decision.mode == "react"


def test_complex_coding_request_escalates_to_plan_and_execute():
    decision = classify_intent("修复登录接口并补充测试")

    assert decision.intent == "coding"
    assert decision.mode == "plan_execute"
    assert decision.score >= 3


def test_high_decision_and_execution_chain_delegates_to_specialists():
    decision = classify_intent("设计安全的跨文件认证迁移方案，实现完整功能并测试验收性能和兼容性")

    assert decision.mode == "delegate"
    assert decision.execution_chain_length >= 5
    assert decision.suggested_roles == ("researcher", "implementer", "reviewer")


def test_prompt_length_does_not_change_a_direct_question_route():
    decision = classify_intent("请详细解释 Python 的装饰器原理。" * 30)

    assert decision.mode == "direct"


def test_runtime_execution_signals_upgrade_react_to_planning():
    signals = ExecutionSignals(turns=2, tool_calls=5, read_search_calls=3, write_calls=1)
    assert escalation_target(signals) == "plan_execute"


def test_runtime_execution_signals_upgrade_complex_work_to_team():
    signals = ExecutionSignals(turns=3, tool_calls=8, read_search_calls=4, write_calls=2)
    assert escalation_target(signals) == "delegate"


def test_parse_route_result_validates_llm_json_contract():
    decision = parse_route_result(
        '{"intent":"coding","complexity":{"level":"medium","tool_calls":true,"multiple_files":true,"code_changes":true,"multiple_stages":true,"test_validation":true,"cross_role_collaboration":false},"route":"plan_execute",'
        '"requires_tools":true,"requires_code_changes":true,"suggested_roles":[],"reasons":["multi-step"]}'
    )

    assert decision.mode == "plan_execute"
    with pytest.raises(ValueError):
        parse_route_result('{"intent":"chat","complexity":{"level":"low","tool_calls":false,"multiple_files":false,"code_changes":false,"multiple_stages":false,"test_validation":false,"cross_role_collaboration":false},"route":"direct","requires_tools":true,"requires_code_changes":false,"suggested_roles":[],"reasons":[]}')


@pytest.mark.asyncio
async def test_dispatcher_invokes_only_the_selected_workflow():
    calls = []

    async def workflow(name):
        calls.append(name)

    dispatcher = RouteDispatcher(
        direct=lambda task: workflow("direct"),
        react=lambda task: workflow("react"),
        plan_execute=lambda task: workflow("plan"),
        delegate=lambda task: workflow("delegate"),
    )
    decision = classify_intent("设计安全的跨文件认证迁移方案，实现完整功能并测试验收性能和兼容性")
    await dispatcher.dispatch(decision, "task")

    assert calls == ["delegate"]
