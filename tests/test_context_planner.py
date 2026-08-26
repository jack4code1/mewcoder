from mewcode.engine.context import ContextBudget, ContextItem, build_session_state, compact_tool_results_for_context, compress_messages, plan_context
from mewcode.engine.models import Message, MessageRole, ToolCall


def test_context_plan_prefers_higher_priority_items_within_budget():
    plan = plan_context(
        [
            ContextItem("history", "old", priority=1, token_estimate=8),
            ContextItem("system", "rules", priority=10, token_estimate=5),
            ContextItem("memory", "fact", priority=5, token_estimate=4),
        ],
        budget=10,
    )

    assert [item.source for item in plan.included] == ["system", "memory"]
    assert [item.source for item in plan.excluded] == ["history"]
    assert plan.used_tokens == 9


def test_context_budget_reserves_response_capacity():
    budget = ContextBudget(total_tokens=100, reserved_response_tokens=25)

    assert budget.input_tokens == 75
    assert budget.cap(90) == 75


def test_session_state_and_summary_keep_tool_facts_separate_from_recent_messages():
    messages = [
        Message(MessageRole.USER, "Add a health check"),
        Message(MessageRole.ASSISTANT, "", tool_calls=[ToolCall("edit", "EditFile", {"path": "src/app.py"})]),
        Message(MessageRole.TOOL, "File updated", tool_call_id="edit"),
        Message(MessageRole.USER, "Now add tests"),
    ]

    state = build_session_state(messages, {"implement": "completed", "test": "pending"})
    summary = compress_messages(messages, keep_recent=1)

    assert state.goal == "Now add tests"
    assert state.modified_files == ["src/app.py"]
    assert state.task_status == {"implement": "completed", "test": "pending"}
    assert "Important tool results:" in summary.summary.content
    assert "Modified files: src/app.py" in summary.summary.content
    assert "Current workspace, tool observations, and test results take precedence" in state.to_prompt()


def test_large_tool_result_is_compacted_only_for_model_context():
    original = "start\n" + "x" * 3_000 + "\nfinal error: exit 1"
    messages = [Message(MessageRole.TOOL, original, tool_call_id="bash", tool_result_is_error=True)]

    compacted = compact_tool_results_for_context(messages, max_chars=600)

    assert messages[0].content == original
    assert len(compacted[0].content) < 800
    assert "original retained in session" in compacted[0].content
    assert "final error: exit 1" in compacted[0].content
