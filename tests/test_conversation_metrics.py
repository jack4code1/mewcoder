from pathlib import Path
from uuid import uuid4

from mewcode.engine.conversation import Conversation, ConversationManager
from mewcode.engine.models import ApiCallMetrics, Message, MessageRole, TokenUsage


def _workspace_test_dir() -> Path:
    path = Path.cwd() / ".mewcode_test_sessions" / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_conversation_metrics_roundtrip_through_dict():
    conversation = Conversation(conversation_id="conv", title="metrics")
    conversation.add_message(
        Message(
            role=MessageRole.ASSISTANT,
            content="answer",
            token_usage=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        )
    )
    conversation.add_api_call_metrics(
        ApiCallMetrics(
            output_tokens_per_second=10.0,
            ttft_ms=500,
            latency_ms=2500,
            had_usage=True,
            had_first_token=True,
        )
    )

    data = conversation.to_dict()
    restored = Conversation.from_dict(data)

    assert data["total_token_usage"]["total_tokens"] == 30
    assert data["api_metrics"]["api_call_count"] == 1
    assert restored.total_token_usage.total_tokens == 30
    assert restored.api_metrics.average_output_tokens_per_second == 10.0
    assert restored.api_metrics.average_ttft_ms == 500
    assert restored.api_metrics.average_latency_ms == 2500


def test_conversation_manager_persists_metrics_to_yaml():
    manager = ConversationManager(storage_dir=str(_workspace_test_dir()))
    conversation = manager.create_conversation("metrics")
    manager.add_message(
        Message(
            role=MessageRole.ASSISTANT,
            content="answer",
            token_usage=TokenUsage(prompt_tokens=3, completion_tokens=7, total_tokens=10),
        )
    )
    manager.add_api_call_metrics(
        ApiCallMetrics(
            output_tokens_per_second=7.0,
            ttft_ms=100,
            latency_ms=1100,
            had_usage=True,
            had_first_token=True,
        )
    )

    assert manager.save_conversation(conversation.id)

    reloaded = ConversationManager(storage_dir=str(manager.storage_dir))
    assert reloaded.load_conversation(conversation.id)

    assert reloaded.get_token_usage().total_tokens == 10
    assert reloaded.get_api_metrics().api_call_count == 1
    assert reloaded.get_api_metrics().average_output_tokens_per_second == 7.0


def test_old_conversation_without_api_metrics_still_loads():
    data = {
        "id": "legacy",
        "title": "legacy",
        "messages": [],
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
        "total_token_usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }

    conversation = Conversation.from_dict(data)

    assert conversation.api_metrics.api_call_count == 0
