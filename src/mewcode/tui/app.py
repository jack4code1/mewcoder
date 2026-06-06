"""MewCode TUI Application"""

import asyncio
import logging
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header

from ..config import get_model_config, load_config
from ..engine.adapters import AdapterFactory
from ..engine.conversation import ConversationManager
from ..engine.models import Message, MessageRole
from ..logger import logger
from .widgets.chat_area import ChatArea
from .widgets.input_box import InputBox, InputSubmitted, TabPressed
from .widgets.status_bar import StatusBar


class MewCodeApp(App):
    """MewCode TUI 主应用"""

    CSS = """
    Screen {
        layout: vertical;
    }

    #chat-area {
        height: 1fr;
        border: solid $primary;
        margin: 0 1;
    }

    #chat-scroll {
        height: 1fr;
        overflow-y: auto;
        background: $surface;
    }

    .chat-msg {
        margin: 0 1;
        padding: 0 1;
    }

    #input-box {
        height: auto;
        max-height: 10;
        border: solid $primary;
        margin: 0 1;
    }

    #input-field {
        background: $surface;
    }

    #prompt {
        background: $surface;
    }

    #status-bar {
        height: auto;
        dock: bottom;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+l", "clear_screen", "Clear"),
        Binding("ctrl+s", "save_session", "Save"),
        Binding("ctrl+o", "switch_model", "Model"),
        Binding("ctrl+t", "toggle_mode", "Mode"),
        Binding("ctrl+shift+c", "copy_last_reply", "Copy"),
        Binding("f1", "show_help", "Help"),
        Binding("ctrl+h", "show_help", "Help"),
    ]

    def __init__(self, model: str = None, provider: str = None, **kwargs):
        super().__init__(**kwargs)
        self.config = load_config()
        default_model = self.config.get("llm", {}).get("default_model", "gpt-4")
        default_provider = self.config.get("llm", {}).get("default_provider")
        self.model = model or default_model
        self.provider = provider or default_provider
        self.conversation_manager = ConversationManager()
        self.llm_client = None
        self.mode = "Chat"  # Chat or Single
        self.is_processing = False

    def compose(self) -> ComposeResult:
        """Compose the TUI layout"""
        yield Header()
        yield Vertical(
            ChatArea(id="chat-area"),
            InputBox(id="input-box"),
        )
        yield StatusBar(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize on mount"""
        # Create initial conversation
        self.conversation_manager.create_conversation()

        # Update status bar
        status_bar = self.query_one("#status-bar", StatusBar)
        status_bar.update_model(self.model)
        status_bar.update_mode(self.mode)

        # Show welcome message
        chat_area = self.query_one("#chat-area", ChatArea)
        chat_area.add_system_message("Welcome to MewCode! Type your message or /help for commands.")

    async def on_unmount(self) -> None:
        """App closing — release LLM client resources"""
        if self.llm_client is not None:
            try:
                await self.llm_client.close()
            except Exception:
                pass

    def on_input_submitted(self, event: InputSubmitted) -> None:
        """Handle input submission"""
        value = event.value

        # Check for commands
        if value.startswith("/"):
            self._handle_command(value)
        else:
            self._handle_message(value)

    def on_tab_pressed(self, event: TabPressed) -> None:
        """Handle tab press for prompt optimization"""
        value = event.value
        if value:
            # Simple prompt optimization - in production, you'd want to use LLM
            optimized = f"Please help me with the following: {value}"
            input_box = self.query_one("#input-box", InputBox)
            input_field = input_box.query_one("#input-field")
            input_field.value = optimized

    def _handle_command(self, command: str) -> None:
        """Handle commands"""
        chat_area = self.query_one("#chat-area", ChatArea)
        command = command.lower().strip()

        if command == "/help":
            chat_area.add_system_message(
                "Available commands:\n"
                "  /help    - Show this help\n"
                "  /copy    - Copy last AI reply to clipboard\n"
                "  /clear   - Clear chat\n"
                "  /save    - Save session\n"
                "  /model   - Switch model\n"
                "  /mode    - Toggle mode\n"
                "  /quit    - Exit application"
            )
        elif command == "/copy":
            self._copy_last_reply()
        elif command == "/clear":
            chat_area.clear()
            chat_area.add_system_message("Chat cleared.")
        elif command == "/save":
            self.action_save_session()
        elif command == "/model":
            self.action_switch_model()
        elif command == "/mode":
            self.action_toggle_mode()
        elif command == "/quit":
            self.action_quit()
        else:
            chat_area.add_system_message(f"Unknown command: {command}")

    def _copy_last_reply(self) -> None:
        """复制最后一条 AI 回复到剪贴板"""
        chat_area = self.query_one("#chat-area", ChatArea)
        messages = chat_area._messages
        # 从后往前找最后一条 assistant 消息
        for msg in reversed(messages):
            if msg["role"] == "assistant":
                self.copy_to_clipboard(msg["content"])
                chat_area.add_system_message("Last AI reply copied to clipboard.")
                return
        chat_area.add_system_message("No AI reply to copy.")

    def _handle_message(self, content: str) -> None:
        """Handle user message"""
        logger.info(f"Handling message: {content[:50]}...")

        if self.is_processing:
            logger.warning("Already processing, skipping message")
            return

        chat_area = self.query_one("#chat-area", ChatArea)
        status_bar = self.query_one("#status-bar", StatusBar)

        # Add user message to chat
        chat_area.add_user_message(content)

        # Add to conversation manager
        user_message = Message(role=MessageRole.USER, content=content)
        self.conversation_manager.add_message(user_message)

        # Update token usage
        token_usage = self.conversation_manager.get_token_usage()
        status_bar.update_token_usage(token_usage.total_tokens, 0)

        # Process with LLM using run_worker
        logger.info("Starting LLM worker...")
        self.run_worker(self._process_with_llm(content), exclusive=True)

    async def _process_with_llm(self, content: str) -> None:
        """Process message with LLM"""
        logger.info("Starting LLM processing...")
        self.is_processing = True
        chat_area = self.query_one("#chat-area", ChatArea)
        status_bar = self.query_one("#status-bar", StatusBar)

        try:
            # Update status
            status_bar.update_agent_status("Thinking...")
            logger.info("Status updated to Thinking...")

            # Get or create LLM client
            if self.llm_client is None:
                logger.info(f"Creating LLM client: model={self.model}, provider={self.provider}")
                try:
                    model_cfg = get_model_config(self.config, self.model)
                    self.llm_client = AdapterFactory.create_client(
                        model=self.model,
                        provider=self.provider or model_cfg.get("provider"),
                        api_key=model_cfg.get("api_key"),
                        base_url=model_cfg.get("base_url"),
                        api_format=model_cfg.get("api_format", "openai"),
                    )
                    logger.info("LLM client created successfully")
                except Exception as e:
                    logger.error(f"Error creating LLM client: {e}")
                    chat_area.add_system_message(f"Error creating LLM client: {e}")
                    return

            # Get messages
            messages = self.conversation_manager.get_messages()
            logger.info(f"Got {len(messages)} messages")

            # Stream response
            full_response = ""
            chat_area.add_assistant_message_start()
            logger.info("Starting stream...")

            async for chunk in self.llm_client.chat_stream(messages):
                if chunk.content:
                    full_response += chunk.content
                    chat_area.add_stream_chunk(chunk.content)
                    logger.debug(f"Chunk: {chunk.content[:20]}...")

            chat_area.add_assistant_message_end()
            logger.info(f"Stream completed. Response length: {len(full_response)}")

            # Add assistant message to conversation
            assistant_message = Message(
                role=MessageRole.ASSISTANT,
                content=full_response,
            )
            self.conversation_manager.add_message(assistant_message)

            # Update status
            status_bar.update_agent_status("Idle")
            logger.info("Processing completed successfully")

        except Exception as e:
            logger.error(f"Error in LLM processing: {e}", exc_info=True)
            chat_area.add_system_message(f"Error: {e}")
            status_bar.update_agent_status("Error")

        finally:
            self.is_processing = False
            logger.info("is_processing set to False")

    def action_copy_last_reply(self) -> None:
        """Copy last AI reply (快捷键触发)"""
        self._copy_last_reply()

    def action_clear_screen(self) -> None:
        """Clear the chat screen"""
        chat_area = self.query_one("#chat-area", ChatArea)
        chat_area.clear()

    def action_save_session(self) -> None:
        """Save current session"""
        self.conversation_manager.save_conversation()
        self.notify("Session saved")

    def action_switch_model(self) -> None:
        """Switch LLM model"""
        # TODO: Implement model switching dialog
        self.notify("Model switching not implemented yet")

    def action_toggle_mode(self) -> None:
        """Toggle between chat and single mode"""
        if self.mode == "Chat":
            self.mode = "Single"
        else:
            self.mode = "Chat"

        status_bar = self.query_one("#status-bar", StatusBar)
        status_bar.update_mode(self.mode)
        self.notify(f"Mode: {self.mode}")

    def action_show_help(self) -> None:
        """Show help dialog"""
        self._handle_command("/help")


def run_app(model: str = None, provider: str = None):
    """Run the MewCode TUI application"""
    app = MewCodeApp(model=model, provider=provider)
    app.run()
