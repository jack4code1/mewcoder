"""Conversation manager for MewCode"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from .models.message import Message, MessageRole, TokenUsage


class Conversation:
    """单个对话"""

    def __init__(self, conversation_id: Optional[str] = None, title: str = ""):
        self.id = conversation_id or str(uuid.uuid4())
        self.title = title or f"Conversation {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        self.messages: list[Message] = []
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.total_token_usage = TokenUsage()

    def add_message(self, message: Message) -> None:
        """添加消息"""
        self.messages.append(message)
        self.updated_at = datetime.now()

        if message.token_usage:
            self.total_token_usage = self.total_token_usage + message.token_usage

    def get_messages(self, limit: Optional[int] = None) -> list[Message]:
        """获取消息列表"""
        if limit:
            return self.messages[-limit:]
        return self.messages

    def clear(self) -> None:
        """清空消息"""
        self.messages = []
        self.total_token_usage = TokenUsage()
        self.updated_at = datetime.now()

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "messages": [msg.to_dict() for msg in self.messages],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "total_token_usage": {
                "prompt_tokens": self.total_token_usage.prompt_tokens,
                "completion_tokens": self.total_token_usage.completion_tokens,
                "total_tokens": self.total_token_usage.total_tokens,
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Conversation":
        """从字典创建对话"""
        conv = cls(conversation_id=data["id"], title=data["title"])
        conv.created_at = datetime.fromisoformat(data["created_at"])
        conv.updated_at = datetime.fromisoformat(data["updated_at"])

        usage = data.get("total_token_usage", {})
        conv.total_token_usage = TokenUsage(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )

        for msg_data in data.get("messages", []):
            conv.messages.append(Message.from_dict(msg_data))

        return conv


class ConversationManager:
    """对话管理器"""

    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = Path(storage_dir or "~/.mewcode/sessions").expanduser()
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.conversations: dict[str, Conversation] = {}
        self.active_conversation_id: Optional[str] = None

    def create_conversation(self, title: str = "") -> Conversation:
        """创建新对话"""
        conv = Conversation(title=title)
        self.conversations[conv.id] = conv
        self.active_conversation_id = conv.id
        return conv

    def get_active_conversation(self) -> Optional[Conversation]:
        """获取当前活跃对话"""
        if self.active_conversation_id:
            return self.conversations.get(self.active_conversation_id)
        return None

    def set_active_conversation(self, conversation_id: str) -> bool:
        """设置活跃对话"""
        if conversation_id in self.conversations:
            self.active_conversation_id = conversation_id
            return True
        return False

    def add_message(self, message: Message, conversation_id: Optional[str] = None) -> None:
        """添加消息到指定对话"""
        conv_id = conversation_id or self.active_conversation_id
        if conv_id and conv_id in self.conversations:
            self.conversations[conv_id].add_message(message)

    def get_messages(self, limit: Optional[int] = None, conversation_id: Optional[str] = None) -> list[Message]:
        """获取消息列表"""
        conv_id = conversation_id or self.active_conversation_id
        if conv_id and conv_id in self.conversations:
            return self.conversations[conv_id].get_messages(limit)
        return []

    def list_conversations(self) -> list[dict]:
        """列出所有对话"""
        return [
            {
                "id": conv.id,
                "title": conv.title,
                "message_count": len(conv.messages),
                "updated_at": conv.updated_at.isoformat(),
            }
            for conv in self.conversations.values()
        ]

    def delete_conversation(self, conversation_id: str) -> bool:
        """删除对话"""
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
            if self.active_conversation_id == conversation_id:
                self.active_conversation_id = None
            return True
        return False

    def save_conversation(self, conversation_id: Optional[str] = None) -> bool:
        """保存对话到文件"""
        conv_id = conversation_id or self.active_conversation_id
        if conv_id and conv_id in self.conversations:
            conv = self.conversations[conv_id]
            file_path = self.storage_dir / f"{conv.id}.yaml"

            with open(file_path, "w", encoding="utf-8") as f:
                yaml.dump(conv.to_dict(), f, allow_unicode=True, default_flow_style=False)

            return True
        return False

    def load_conversation(self, conversation_id: str) -> bool:
        """从文件加载对话"""
        file_path = self.storage_dir / f"{conversation_id}.yaml"

        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            conv = Conversation.from_dict(data)
            self.conversations[conv.id] = conv
            self.active_conversation_id = conv.id
            return True
        return False

    def load_all_conversations(self) -> int:
        """加载所有保存的对话"""
        count = 0
        for file_path in self.storage_dir.glob("*.yaml"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                conv = Conversation.from_dict(data)
                self.conversations[conv.id] = conv
                count += 1
            except Exception:
                continue

        return count

    def get_token_usage(self, conversation_id: Optional[str] = None) -> TokenUsage:
        """获取 Token 用量"""
        conv_id = conversation_id or self.active_conversation_id
        if conv_id and conv_id in self.conversations:
            return self.conversations[conv_id].total_token_usage
        return TokenUsage()
