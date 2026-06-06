"""End-to-end tests for MewCode"""

import asyncio
import os

import pytest

from mewcode.engine.adapters import AdapterFactory
from mewcode.engine.conversation import ConversationManager
from mewcode.engine.models import Message, MessageRole, TokenUsage


class TestConversationManager:
    """Test ConversationManager"""

    def test_create_conversation(self):
        """Test creating a conversation"""
        cm = ConversationManager()
        conv = cm.create_conversation("Test")
        assert conv.title == "Test"
        assert conv.id is not None

    def test_add_message(self):
        """Test adding a message"""
        cm = ConversationManager()
        conv = cm.create_conversation("Test")

        message = Message(role=MessageRole.USER, content="Hello")
        cm.add_message(message)

        messages = cm.get_messages()
        assert len(messages) == 1
        assert messages[0].content == "Hello"

    def test_token_usage(self):
        """Test token usage tracking"""
        cm = ConversationManager()
        conv = cm.create_conversation("Test")

        message = Message(
            role=MessageRole.USER,
            content="Hello",
            token_usage=TokenUsage(prompt_tokens=10, completion_tokens=0, total_tokens=10),
        )
        cm.add_message(message)

        usage = cm.get_token_usage()
        assert usage.total_tokens == 10


class TestAdapterFactory:
    """Test AdapterFactory"""

    def test_detect_provider_openai(self):
        """Test detecting OpenAI provider"""
        assert AdapterFactory.detect_provider("gpt-4") == "openai"
        assert AdapterFactory.detect_provider("gpt-3.5-turbo") == "openai"

    def test_detect_provider_claude(self):
        """Test detecting Claude provider"""
        assert AdapterFactory.detect_provider("claude-3-5-sonnet") == "claude"
        assert AdapterFactory.detect_provider("claude-3-opus") == "claude"

    def test_detect_provider_ollama(self):
        """Test detecting Ollama provider"""
        assert AdapterFactory.detect_provider("llama2") == "ollama"
        assert AdapterFactory.detect_provider("mistral") == "ollama"

    def test_list_providers(self):
        """Test listing providers"""
        providers = AdapterFactory.list_providers()
        assert "openai" in providers
        assert "claude" in providers
        assert "ollama" in providers
        assert "custom" in providers


class TestMessage:
    """Test Message data class"""

    def test_message_creation(self):
        """Test creating a message"""
        message = Message(role=MessageRole.USER, content="Hello")
        assert message.role == MessageRole.USER
        assert message.content == "Hello"

    def test_message_to_dict(self):
        """Test converting message to dict"""
        message = Message(role=MessageRole.USER, content="Hello")
        data = message.to_dict()
        assert data["role"] == "user"
        assert data["content"] == "Hello"

    def test_message_from_dict(self):
        """Test creating message from dict"""
        data = {
            "role": "user",
            "content": "Hello",
            "timestamp": "2024-01-01T00:00:00",
        }
        message = Message.from_dict(data)
        assert message.role == MessageRole.USER
        assert message.content == "Hello"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
