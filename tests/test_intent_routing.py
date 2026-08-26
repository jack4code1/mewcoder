from mewcode.engine.orchestration import classify_intent


def test_simple_request_stays_in_react_mode():
    decision = classify_intent("读取 config.yaml 并告诉我默认模型")

    assert decision.intent == "conversation"
    assert decision.mode == "react"


def test_complex_coding_request_escalates_to_plan_and_execute():
    decision = classify_intent("实现完整的用户认证功能，修改多个文件，并且补充端到端测试")

    assert decision.intent == "coding"
    assert decision.mode == "plan_execute"
    assert decision.score >= 3
