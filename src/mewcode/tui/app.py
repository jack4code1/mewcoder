"""MewCode TUI Application"""

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
from ..engine.models import Message, MessageRole, ToolCall
from ..engine.tools import (
    ToolContext,
    ToolResult,
    build_default_registry,
    build_system_prompt,
)
from ..logger import logger
from .widgets.chat_area import ChatArea
from .widgets.input_box import InputBox, InputSubmitted, TabPressed
from .widgets.status_bar import StatusBar


def _summarize_tool_input(name: str, input: dict) -> str:
    """Produce a short, human-readable summary for the TUI trace line."""
    if not isinstance(input, dict):
        return ""
    if name == "ReadFile":
        return str(input.get("path", ""))
    if name == "WriteFile":
        return str(input.get("path", ""))
    if name == "EditFile":
        return str(input.get("path", ""))
    if name == "Bash":
        cmd = str(input.get("command", ""))
        return cmd[:60] + ("..." if len(cmd) > 60 else "")
    if name == "Glob":
        return str(input.get("pattern", ""))
    if name == "Grep":
        return str(input.get("pattern", ""))
    # fallback: first scalar value
    for v in input.values():
        if isinstance(v, (str, int, float, bool)):
            return str(v)[:60]
    return ""


def _summarize_tool_result(content: str) -> str:
    """First non-empty line of the tool's result, capped."""
    if not content:
        return ""
    line = content.splitlines()[0].strip()
    return line[:80] + ("..." if len(line) > 80 else "")


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

    .tool-msg {
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

        # Tool subsystem (chapter 02-tools): locked at startup
        self.tool_context: ToolContext = ToolContext.detect(
            working_dir=Path(os.getcwd())
        )
        self.tool_registry = build_default_registry(self.tool_context, self.config)
        logger.info(
            "Tool registry initialised: %s",
            [t.name for t in self.tool_registry.list_enabled()],
        )

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

    # ------------------------------------------------------------------
    # LLM driver: single-step tool flow (chapter 02-tools)
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
        """Drive the single-step tool flow.

        Step A — first stream:
          - Render text deltas in the chat area.
          - Capture the final StreamChunk's tool_calls (if any).
          - Persist the assistant message (with tool_calls) into history.
        Step B — execute each tool call serially:
          - Show the trace line, run the tool, update the trace line.
          - Persist the TOOL-role result message into history.
        Step C — second stream:
          - Stream and render the model's final reply.
          - Persist as a plain assistant message. Even if the model emits
            tool_calls again, we IGNORE them this chapter (single-step gate,
            spec AC17).

        If step A produces no tool_calls, step B/C are skipped — pure-chat
        behaviour from chapter 01 is preserved exactly.
        """
        logger.info("Starting LLM processing...")
        self.is_processing = True
        chat_area = self.query_one("#chat-area", ChatArea)
        status_bar = self.query_one("#status-bar", StatusBar)

        try:
            status_bar.update_agent_status("Thinking...")

            if not self._ensure_llm_client():
                return

            tools_payload = self._build_tools_payload()

            # ---------- Step A: first stream ----------
            chat_area.add_assistant_message_start()
            first_text = ""
            pending_tool_calls: list[ToolCall] = []
            async for chunk in self.llm_client.chat_stream(
                self._messages_with_system(), tools=tools_payload
            ):
                if chunk.content:
                    first_text += chunk.content
                    chat_area.add_stream_chunk(chunk.content)
                if chunk.tool_calls:
                    # Last non-empty wins — adapters emit one final chunk.
                    pending_tool_calls = list(chunk.tool_calls)
            chat_area.add_assistant_message_end()

            self.conversation_manager.add_message(
                Message(
                    role=MessageRole.ASSISTANT,
                    content=first_text,
                    tool_calls=pending_tool_calls or None,
                )
            )

            if not pending_tool_calls:
                status_bar.update_agent_status("Idle")
                return

            # ---------- Step B: execute each tool ----------
            for tc in pending_tool_calls:
                params_summary = _summarize_tool_input(tc.name, tc.input)
                widget_id = chat_area.add_tool_call(tc.name, params_summary)

                if tc.parse_error:
                    result = ToolResult(
                        content=f"Tool arguments could not be parsed: {tc.parse_error}",
                        is_error=True,
                        metadata={"tool": tc.name},
                    )
                else:
                    try:
                        result = await self.tool_registry.execute(tc.name, tc.input)
                    except Exception as e:  # ToolError or anything else
                        logger.exception("Unexpected tool dispatch failure")
                        result = ToolResult(
                            content=f"Tool dispatch failed: {e}",
                            is_error=True,
                            metadata={"tool": tc.name},
                        )

                chat_area.update_tool_call_result(
                    widget_id,
                    success=not result.is_error,
                    summary=_summarize_tool_result(result.content),
                )
                self.conversation_manager.add_message(
                    Message(
                        role=MessageRole.TOOL,
                        content=result.content,
                        tool_call_id=tc.id,
                        tool_result_is_error=bool(result.is_error),
                    )
                )

            # ---------- Step C: second stream (final reply) ----------
            chat_area.add_assistant_message_start()
            final_text = ""
            ignored_tool_calls = False
            async for chunk in self.llm_client.chat_stream(
                self._messages_with_system(), tools=tools_payload
            ):
                if chunk.content:
                    final_text += chunk.content
                    chat_area.add_stream_chunk(chunk.content)
                if chunk.tool_calls:
                    # Single-step gate: ignore. (spec AC17)
                    ignored_tool_calls = True
            chat_area.add_assistant_message_end()

            if ignored_tool_calls:
                logger.info(
                    "Second response contained tool_calls; ignored (single-step gate)."
                )

            self.conversation_manager.add_message(
                Message(role=MessageRole.ASSISTANT, content=final_text)
            )

            status_bar.update_agent_status("Idle")
            logger.info("Processing completed (single-step tool flow).")

        except Exception as e:
            logger.error("Error in LLM processing: %s", e, exc_info=True)
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
