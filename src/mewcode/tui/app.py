"""MewCode TUI Application"""

import asyncio
import os
from datetime import datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header

from ..config import get_model_config, get_tools_config, load_config
from ..engine.adapters import AdapterFactory
from ..engine.adapters.claude_adapter import ClaudeAdapter
from ..engine.conversation import ConversationManager
from ..engine.agent import run_agent_loop
from ..engine.agent_events import AgentEventType, AgentStopReason
from ..engine.models import Message, MessageRole, TokenUsage
from ..engine.tools import (
    ToolContext,
    build_default_registry,
    build_system_prompt,
)
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
        margin: 0 1 0 1;
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

    .tool-msg {
        margin: 0 1;
        padding: 0 1;
    }

    #main-layout {
        height: 1fr;
    }

    #input-box {
        height: 4;
        min-height: 4;
        max-height: 4;
        border: solid $primary;
        margin: 1 1 0 1;
        padding: 0 1;
    }

    #input-field {
        background: $surface;
    }

    #prompt {
        background: $surface;
        width: 4;
    }

    #status-bar {
        height: 1;
        min-height: 1;
        margin: 0 1;
        background: $surface;
    }

    #status-label {
        height: 1;
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+l", "clear_screen", "Clear"),
        Binding("ctrl+s", "save_session", "Save"),
        Binding("ctrl+o", "switch_model", "Model"),
        Binding("ctrl+t", "toggle_mode", "Mode"),
        Binding("ctrl+shift+c", "copy_last_reply", "Copy"),
        Binding("escape", "cancel_agent", "Cancel"),
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
        self._agent_cancel_event: asyncio.Event | None = None

        # Tool subsystem (chapter 02-tools): locked at startup
        self.tool_context: ToolContext = ToolContext.detect(
            working_dir=Path(os.getcwd())
        )
        self.tool_registry = build_default_registry(self.tool_context, self.config)
        logger.info(
            "Tool registry initialised: %s",
            [t.name for t in self.tool_registry.list_enabled()],
        )

    @staticmethod
    def _has_usage(usage: TokenUsage) -> bool:
        return bool(usage.prompt_tokens or usage.completion_tokens or usage.total_tokens)

    def compose(self) -> ComposeResult:
        """Compose the TUI layout"""
        yield Header()
        yield Vertical(
            ChatArea(id="chat-area"),
            InputBox(id="input-box"),
            StatusBar(id="status-bar"),
            id="main-layout",
        )
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
            self.notify("A request is already running. Press Esc to cancel it.")
            return

        chat_area = self.query_one("#chat-area", ChatArea)
        status_bar = self.query_one("#status-bar", StatusBar)

        # Add user message to chat
        chat_area.add_user_message(content)

        # Add to conversation manager
        user_message = Message(role=MessageRole.USER, content=content)
        self.conversation_manager.add_message(user_message)

        # Update restored nonzero token usage without inventing a zero value.
        token_usage = self.conversation_manager.get_token_usage()
        api_metrics = self.conversation_manager.get_api_metrics()
        if self._has_usage(token_usage) or api_metrics.usage_call_count > 0:
            status_bar.update_token_usage(token_usage)
        if api_metrics.api_call_count > 0:
            status_bar.update_metrics(api_metrics)

        # Process with LLM using run_worker
        logger.info("Starting LLM worker...")
        self.run_worker(self._process_with_llm(content), exclusive=True)

    # ------------------------------------------------------------------
    # LLM driver: Agent Loop event consumer
    # ------------------------------------------------------------------

    def _build_tools_payload(self) -> list[dict]:
        """Pick the tools-API format that matches the active adapter."""
        if isinstance(self.llm_client, ClaudeAdapter):
            return self.tool_registry.to_anthropic_format()
        return self.tool_registry.to_openai_format()

    def _ensure_llm_client(self) -> bool:
        """Lazily create the LLM client on first use. Returns True on success."""
        if self.llm_client is not None:
            return True
        chat_area = self.query_one("#chat-area", ChatArea)
        try:
            model_cfg = get_model_config(self.config, self.model)
            self.llm_client = AdapterFactory.create_client(
                model=self.model,
                provider=self.provider or model_cfg.get("provider"),
                api_key=model_cfg.get("api_key"),
                base_url=model_cfg.get("base_url"),
                api_format=model_cfg.get("api_format", "openai"),
            )
            logger.info("LLM client created: %s", type(self.llm_client).__name__)
            return True
        except Exception as e:
            logger.error("Error creating LLM client: %s", e, exc_info=True)
            chat_area.add_system_message(f"Error creating LLM client: {e}")
            return False

    def _messages_with_system(self) -> list[Message]:
        """Return current conversation messages with the tool system prompt
        prepended for *this* request only. The system prompt is rebuilt
        every call so cwd/OS/tool list stay accurate, and is NOT persisted
        into the conversation history."""
        sys_text = build_system_prompt(self.tool_context, self.tool_registry)
        sys_msg = Message(role=MessageRole.SYSTEM, content=sys_text)
        return [sys_msg] + self.conversation_manager.get_messages()

    async def _process_with_llm(self, content: str) -> None:
        """Consume Agent Loop events and update the TUI."""
        logger.info("Starting LLM processing...")
        self.is_processing = True
        self._agent_cancel_event = asyncio.Event()
        chat_area = self.query_one("#chat-area", ChatArea)
        status_bar = self.query_one("#status-bar", StatusBar)

        try:
            status_bar.update_agent_status("Thinking...")

            if not self._ensure_llm_client():
                return

            tool_widgets: dict[str, str] = {}
            is_streaming = False

            async for event in run_agent_loop(
                llm_client=self.llm_client,
                conversation_manager=self.conversation_manager,
                tool_registry=self.tool_registry,
                tools_payload=self._build_tools_payload(),
                build_messages=self._messages_with_system,
                cancel_event=self._agent_cancel_event,
            ):
                if event.event_type == AgentEventType.STREAM_TEXT:
                    if not is_streaming:
                        chat_area.add_assistant_message_start()
                        is_streaming = True
                    chat_area.add_stream_chunk(event.text)

                elif event.event_type == AgentEventType.TURN_COMPLETE:
                    if is_streaming:
                        chat_area.add_assistant_message_end()
                        is_streaming = False
                    status_bar.update_agent_status("Thinking...")

                elif event.event_type == AgentEventType.TOOL_USE:
                    status_bar.update_agent_status(f"Running {event.tool_name}...")
                    widget_id = chat_area.add_tool_call(
                        event.tool_name or "tool", event.summary
                    )
                    if event.tool_call_id:
                        tool_widgets[event.tool_call_id] = widget_id

                elif event.event_type == AgentEventType.TOOL_RESULT:
                    widget_id = tool_widgets.get(event.tool_call_id or "")
                    if widget_id:
                        chat_area.update_tool_call_result(
                            widget_id,
                            success=not event.is_error,
                            summary=event.summary,
                        )
                    status_bar.update_agent_status("Thinking...")

                elif event.event_type == AgentEventType.USAGE and event.usage is not None:
                    status_bar.update_token_usage(event.usage)

                elif (
                    event.event_type == AgentEventType.METRICS
                    and event.metrics_snapshot is not None
                ):
                    status_bar.update_metrics(event.metrics_snapshot)

                elif event.event_type == AgentEventType.ERROR:
                    if is_streaming:
                        chat_area.add_assistant_message_end()
                        is_streaming = False
                    chat_area.add_system_message(f"Error: {event.message}")
                    status_bar.update_agent_status("Error")

                elif event.event_type == AgentEventType.LOOP_COMPLETE:
                    if is_streaming:
                        chat_area.add_assistant_message_end()
                        is_streaming = False
                    if event.stop_reason == AgentStopReason.CANCELLED:
                        chat_area.add_system_message("Agent cancelled.")
                    status_bar.update_agent_status("Idle")

            logger.info("Processing completed (Agent Loop).")

        except Exception as e:
            logger.error("Error in LLM processing: %s", e, exc_info=True)
            chat_area.add_system_message(f"Error: {e}")
            status_bar.update_agent_status("Error")

        finally:
            self.is_processing = False
            self._agent_cancel_event = None
            logger.info("is_processing set to False")

    def action_cancel_agent(self) -> None:
        """Cancel the active agent loop without quitting the app."""
        if self.is_processing and self._agent_cancel_event is not None:
            self._agent_cancel_event.set()
            status_bar = self.query_one("#status-bar", StatusBar)
            status_bar.update_agent_status("Cancelling...")
            self.notify("Cancelling current request")
        else:
            self.notify("No active request to cancel")

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
