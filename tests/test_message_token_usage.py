from datetime import datetime

from mewcode.engine.models import Message, MessageRole, TokenUsage


def test_message_token_usage_roundtrip():
    message = Message(
        role=MessageRole.ASSISTANT,
        content="answer",
        timestamp=datetime.fromisoformat("2026-01-01T00:00:00"),
        token_usage=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    )

    data = message.to_dict()
    restored = Message.from_dict(data)

    assert data["token_usage"] == {
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "total_tokens": 30,
    }
    assert restored.token_usage == TokenUsage(
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
    )


def test_legacy_message_without_token_usage_still_loads():
    restored = Message.from_dict(
        {
            "role": "assistant",
            "content": "answer",
            "timestamp": "2026-01-01T00:00:00",
        }
    )

    assert restored.token_usage is None
