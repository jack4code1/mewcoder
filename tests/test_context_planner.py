from mewcode.engine.context import ContextBudget, ContextItem, plan_context


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
