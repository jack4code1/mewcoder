"""MewCode TUI Application"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header

from ..config import get_mcp_servers, get_model_config, get_tools_config, load_config
from ..engine.adapters import AdapterFactory
from ..engine.adapters.claude_adapter import ClaudeAdapter
from ..engine.conversation import ConversationManager
from ..engine.agent import run_agent_loop
from ..engine.agent_events import AgentEventType, AgentStopReason
from ..engine.security.gateway import ExecutionGateway
from ..engine.security.audit import AuditLog
from ..engine.security.revisions import RevisionStore
from ..engine.runtime import ProjectRuntime
from ..engine.context import ContextItem, ProjectMemoryStore, embed_with_provider, plan_context
from ..engine.context import MemoryRecord
from ..engine.context import compress_messages
from ..engine.extensions import ProjectHookStore, ProjectSkillStore, SkillRunner
from ..engine.extensions import CommandCatalog
from ..engine.models import Message, MessageRole, TokenUsage
from ..engine.orchestration import (
    AgentAssignment,
    CollaborativeRunner,
    PlanExecutor,
    PlanStep,
    TaskRunner,
    TaskSpec,
    WorktreeManager,
    classify_intent,
    review_passed,
)
from ..engine.mcp import McpServerConfig, McpServerManager
from ..engine.tools import (
    ToolContext,
    build_default_registry,
    build_system_prompt,
)
from ..logger import logger
from .widgets.chat_area import ChatArea
from .widgets.input_box import InputBox, InputContentChanged, InputSubmitted, TabPressed
from .widgets.status_bar import StatusBar
from .widgets.approval_dialog import ApprovalDialog


class MewCodeApp(App):
    """MewCode TUI 主应用"""

    CSS = """
    Screen {
        layout: vertical;
    }

    #chat-area {
        height: 1fr;
        min-height: 3;
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
        height: 5;
        min-height: 3;
        max-height: 5;
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
        height: 3;
        content-align: left middle;
    }

    #status-bar {
        height: 1;
        min-height: 1;
        margin: 0 1;
        background: $surface;
    }

    #status-bar.hidden {
        display: none;
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
        self.project_runtime = ProjectRuntime(self.tool_context.working_dir)
        self.memory_store = ProjectMemoryStore(self.tool_context.working_dir)
        self._memory_query_vector: list[float] | None = None
        self.skill_store = ProjectSkillStore(self.tool_context.working_dir)
        self.skill_runner = SkillRunner()
        self.tool_registry = build_default_registry(self.tool_context, self.config)
        self.worktree_manager = WorktreeManager(self.tool_context.working_dir)
        self.task_runs = []
        self.mcp_manager = McpServerManager([
            McpServerConfig(**server) for server in get_mcp_servers(self.config)
        ])
        self.execution_gateway = None
        self.hook_runner = None
        if self.config.get("security", {}).get("enabled", False):
            self.execution_gateway = ExecutionGateway(
                self.tool_registry, audit_log=AuditLog(self.tool_context.working_dir),
                revisions=RevisionStore(self.tool_context.working_dir),
            )
            self.execution_gateway.grants.load_project(self.tool_context.working_dir)
            self.execution_gateway.grants = self.project_runtime.permissions
            self.hook_runner = ProjectHookStore(self.tool_context.working_dir).build_runner(
                self.execution_gateway
            )
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
            StatusBar(id="status-bar"),
            InputBox(id="input-box"),
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

        # Input is empty at startup -> status bar hidden until the user types.
        status_bar.hide()

    async def on_unmount(self) -> None:
        """App closing — release LLM client resources"""
        if self.llm_client is not None:
            try:
                await self.llm_client.close()
            except Exception:
                pass
        await self.mcp_manager.close()

    def on_input_submitted(self, event: InputSubmitted) -> None:
        """Handle input submission"""
        value = event.value

        # Check for commands
        if value.startswith("/"):
            self._handle_command(value)
        else:
            self._handle_message(value)

    def on_input_content_changed(self, event: InputContentChanged) -> None:
        """Show the status bar while the user is typing, hide it when empty."""
        status_bar = self.query_one("#status-bar", StatusBar)
        if event.has_content:
            status_bar.show()
        else:
            status_bar.hide()

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

        if command.startswith(("/approve", "/deny")) and self.execution_gateway is None:
            chat_area.add_system_message("Security approvals are disabled for this project.")
            return

        if command.startswith("/approve "):
            requested = command.removeprefix("/approve ").strip()
            project_scope = requested.startswith("project ")
            if project_scope:
                requested = requested.removeprefix("project ").strip()
            tool = next(
                (item for item in self.tool_registry.list_enabled() if item.name.lower() == requested),
                None,
            )
            if tool is None:
                chat_area.add_system_message(f"No enabled tool named: {requested}")
            else:
                if project_scope:
                    self.execution_gateway.grants.grant_project(tool.name)
                    self.execution_gateway.grants.save_project(self.tool_context.working_dir)
                else:
                    self.execution_gateway.grants.grant(tool.name)
                chat_area.add_system_message(
                    f"Approved {tool.name} for this {'project' if project_scope else 'session'}."
                )
        elif command.startswith("/approve-request "):
            request_id = command.removeprefix("/approve-request ").strip()
            self.run_worker(self._approve_request(request_id))
            chat_area.add_system_message(f"Approval submitted for {request_id}.")
        elif command.startswith("/approve-project-request "):
            request_id = command.removeprefix("/approve-project-request ").strip()
            self.run_worker(self._approve_request(request_id, project=True))
            chat_area.add_system_message(f"Project approval submitted for {request_id}.")
        elif command.startswith("/deny-request "):
            request_id = command.removeprefix("/deny-request ").strip()
            result = self.execution_gateway.deny(request_id)
            chat_area.add_system_message(result.content)
        elif command == "/audit":
            if self.execution_gateway is None:
                chat_area.add_system_message("Security approvals are disabled for this project.")
            elif not self.execution_gateway.audit:
                chat_area.add_system_message("No security audit entries for this session.")
            else:
                entries = self.execution_gateway.audit[-10:]
                lines = [
                    f"{entry.get('decision', 'unknown')}: {entry.get('tool', 'tool')}"
                    f" ({entry.get('status') or entry.get('reason') or 'recorded'})"
                    for entry in entries
                ]
                chat_area.add_system_message("Recent security audit:\n" + "\n".join(lines))
        elif command == "/diff":
            revisions = self.execution_gateway.revisions.list() if self.execution_gateway and self.execution_gateway.revisions else []
            chat_area.add_system_message("Revisions:\n" + "\n".join(f"- {item.id}: {item.path}" for item in revisions[-10:]) if revisions else "No saved revisions.")
        elif command.startswith("/rollback "):
            revision_id = command.removeprefix("/rollback ").strip()
            store = self.execution_gateway.revisions if self.execution_gateway else None
            revision = store.rollback(revision_id) if store else None
            chat_area.add_system_message(f"Rolled back: {revision.path}" if revision else "No revision found.")
        elif command == "/memory":
            records = self.memory_store.list()
            chat_area.add_system_message(
                "Project memory:\n"
                + "\n".join(f"- {item.id} [{item.kind}]: {item.content}" for item in records)
                if records
                else "Project memory is empty."
            )
        elif command == "/skills":
            skills = self.skill_store.list()
            chat_area.add_system_message(
                "Active project skills:\n"
                + "\n".join(f"- {skill.name}: {skill.source}" for skill in skills)
                if skills
                else "No project skills found."
            )
        elif command.startswith("/skill add "):
            parts = command.removeprefix("/skill add ").strip().split(maxsplit=1)
            if len(parts) != 2:
                chat_area.add_system_message("Usage: /skill add <name> <instructions>")
            else:
                try:
                    skill = self.skill_store.save(parts[0], parts[1])
                    chat_area.add_system_message(f"Saved project skill: {skill.name}")
                except ValueError as exc:
                    chat_area.add_system_message(str(exc))
        elif command.startswith("/skill delete "):
            name = command.removeprefix("/skill delete ").strip()
            chat_area.add_system_message(
                f"Deleted project skill: {name}" if self.skill_store.delete(name) else f"No project skill named: {name}"
            )
        elif command == "/mcp":
            if not self.mcp_manager.status:
                chat_area.add_system_message("No MCP servers configured.")
            else:
                chat_area.add_system_message("MCP servers:\n" + "\n".join(
                    f"- {name}: {status}" for name, status in self.mcp_manager.status.items()
                ))
        elif command.startswith("/mcp connect "):
            name = command.removeprefix("/mcp connect ").strip()
            if name not in self.mcp_manager.servers:
                chat_area.add_system_message(f"No configured MCP server named: {name}")
            elif self.mcp_manager.status.get(name) == "disabled":
                chat_area.add_system_message(f"MCP server {name} is disabled in configuration.")
            else:
                self.run_worker(self._connect_mcp(name))
                chat_area.add_system_message(f"Connecting MCP server: {name}")
        elif command.startswith("/remember "):
            content = command.removeprefix("/remember ").strip()
            if not content:
                chat_area.add_system_message("Usage: /remember <project fact or preference>")
            else:
                record = self.memory_store.save(MemoryRecord(content))
                chat_area.add_system_message(f"Saved project memory: {record.id}")
        elif command.startswith("/forget "):
            record_id = command.removeprefix("/forget ").strip()
            chat_area.add_system_message("Deleted project memory." if self.memory_store.delete(record_id) else "No project memory found with that id.")
        elif command.startswith("/memory search "):
            query = command.removeprefix("/memory search ").strip()
            records = self.memory_store.search(query)
            chat_area.add_system_message(
                "Memory search:\n" + "\n".join(f"- {item.id} [{item.kind}]: {item.content}" for item in records)
                if records else "No matching project memory."
            )
        elif command == "/memory review":
            records = self.memory_store.list("pending")
            chat_area.add_system_message(
                "Memory candidates:\n" + "\n".join(
                    f"- {item.id} [{item.kind}, confidence {item.confidence:.2f}]: {item.content}"
                    for item in records
                ) if records else "No pending memory candidates."
            )
        elif command.startswith("/memory approve "):
            record = self.memory_store.approve(command.removeprefix("/memory approve ").strip())
            chat_area.add_system_message(f"Approved memory: {record.id}" if record else "No pending memory candidate found.")
        elif command.startswith("/memory reject "):
            record_id = command.removeprefix("/memory reject ").strip()
            chat_area.add_system_message("Rejected memory candidate." if self.memory_store.reject(record_id) else "No pending memory candidate found.")
        elif command == "/summarize":
            messages = self.conversation_manager.get_messages()
            summary = compress_messages(messages)
            if summary is None:
                chat_area.add_system_message("Not enough conversation history to summarize.")
            else:
                active = self.conversation_manager.get_active_conversation()
                if active is not None:
                    active.messages = [summary.summary] + messages[-8:]
                chat_area.add_system_message(f"Summarized {summary.source_count} earlier messages.")
        elif command.startswith("/task "):
            objective = command.removeprefix("/task ").strip()
            if not objective:
                chat_area.add_system_message("Usage: /task <objective>")
            elif self.is_processing:
                chat_area.add_system_message("Wait for the active request before starting a task.")
            else:
                self.run_worker(self._run_isolated_task(objective))
                chat_area.add_system_message(f"Starting isolated task: {objective}")
        elif command.startswith("/plan "):
            objective = command.removeprefix("/plan ").strip()
            if not objective:
                chat_area.add_system_message("Usage: /plan <objective>")
            elif self.is_processing:
                chat_area.add_system_message("Wait for the active request before starting a plan.")
            else:
                self.run_worker(self._run_planned_task(objective))
                chat_area.add_system_message(f"Planning task: {objective}")
        elif command.startswith("/team "):
            objective = command.removeprefix("/team ").strip()
            if not objective:
                chat_area.add_system_message("Usage: /team <objective>")
            elif self.is_processing:
                chat_area.add_system_message("Wait for the active request before starting a team.")
            else:
                self.run_worker(self._run_team_task(objective))
                chat_area.add_system_message(f"Starting agent team: {objective}")
        elif command == "/tasks":
            if not self.task_runs:
                chat_area.add_system_message("No isolated tasks have run.")
            else:
                chat_area.add_system_message("Tasks:\n" + "\n".join(
                    f"- {run.id[:8]} {run.status}: {run.result[:120]}" for run in self.task_runs
                ))
        elif command.startswith("/task apply "):
            task_id = command.removeprefix("/task apply ").strip()
            try:
                diff = self.worktree_manager.apply(task_id)
                chat_area.add_system_message(f"Applied task {task_id[:8]}.\n{diff or '(no changes)'}")
            except (ValueError, RuntimeError) as exc:
                chat_area.add_system_message(f"Could not apply task: {exc}")
        elif command.startswith("/task discard "):
            task_id = command.removeprefix("/task discard ").strip()
            try:
                self.worktree_manager.cleanup(task_id)
                chat_area.add_system_message(f"Discarded task {task_id[:8]}.")
            except ValueError as exc:
                chat_area.add_system_message(f"Could not discard task: {exc}")
        elif command == "/context":
            chat_area.add_system_message(self._context_summary())
        elif command.startswith("/deny "):
            requested = command.removeprefix("/deny ").strip()
            project_scope = requested.startswith("project ")
            if project_scope:
                requested = requested.removeprefix("project ").strip()
            for tool in self.tool_registry.list_enabled():
                if tool.name.lower() == requested:
                    if project_scope:
                        self.execution_gateway.grants.revoke_project(tool.name)
                        self.execution_gateway.grants.save_project(self.tool_context.working_dir)
                    else:
                        self.execution_gateway.grants.revoke(tool.name)
                    chat_area.add_system_message(
                        f"Revoked {'project' if project_scope else 'session'} approval for {tool.name}."
                    )
                    break
            else:
                chat_area.add_system_message(f"No enabled tool named: {requested}")
        elif command == "/help":
            commands = CommandCatalog().definitions()
            chat_area.add_system_message(
                "Available commands:\n"
                + "\n".join(f"  {item.name} - {item.description}" for item in commands)
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

    async def _approve_request(self, request_id: str, project: bool = False) -> None:
        result = await self.execution_gateway.approve(request_id, project=project)
        if project and not result.is_error:
            self.execution_gateway.grants.save_project(self.tool_context.working_dir)
        chat_area = self.query_one("#chat-area", ChatArea)
        chat_area.add_system_message(result.content)

    def _show_approval_dialog(
        self,
        request_id: str,
        tool_name: str,
        summary: str,
        approval: dict | None = None,
    ) -> None:
        """Open the keyboard-first approval UI for a pending request."""
        self.push_screen(
            ApprovalDialog(tool_name, summary, approval),
            lambda choice: self._resolve_approval_choice(request_id, choice),
        )

    def _resolve_approval_choice(self, request_id: str, choice: str | None) -> None:
        if self.execution_gateway is None:
            return
        chat_area = self.query_one("#chat-area", ChatArea)
        if choice == "deny" or choice is None:
            chat_area.add_system_message(self.execution_gateway.deny(request_id).content)
        else:
            self.run_worker(self._approve_request(request_id, project=choice == "project"))
        self.call_after_refresh(self._focus_input)

    def _focus_input(self) -> None:
        self.query_one("#input-box", InputBox).query_one("#input-field").focus()

    async def _connect_mcp(self, name: str) -> None:
        chat_area = self.query_one("#chat-area", ChatArea)
        try:
            count = await self.mcp_manager.connect_and_register(name, self.tool_registry)
            chat_area.add_system_message(f"MCP server {name} ready with {count} tools.")
        except Exception as exc:
            chat_area.add_system_message(f"MCP server {name} failed: {exc}")

    async def _run_isolated_task(self, objective: str) -> None:
        chat_area = self.query_one("#chat-area", ChatArea)
        if not self._ensure_llm_client():
            return
        original_gateway = self.execution_gateway

        async def worker(spec, lease):
            context = ToolContext.detect(lease.path)
            registry = build_default_registry(context, self.config)
            gateway = ExecutionGateway(
                registry,
                grants=self.project_runtime.permissions,
                audit_log=AuditLog(lease.path),
                revisions=RevisionStore(lease.path),
            )
            self.execution_gateway = gateway
            text = ""
            async for event in run_agent_loop(
                llm_client=self.llm_client,
                conversation_manager=ConversationManager(storage_dir=str(lease.path / ".mewcode" / "sessions")),
                tool_registry=registry,
                tools_payload=registry.to_openai_format(),
                build_messages=lambda: [Message(MessageRole.SYSTEM, build_system_prompt(context, registry)), Message(MessageRole.USER, spec.objective)],
                execution_gateway=gateway,
            ):
                if event.event_type == AgentEventType.STREAM_TEXT:
                    text += event.text
                elif event.event_type == AgentEventType.APPROVAL_REQUIRED:
                    chat_area.add_approval_request(
                        event.request_id or "unknown", event.tool_name or "tool", event.summary, event.approval
                    )
                    if event.request_id:
                        self._show_approval_dialog(
                            event.request_id,
                            event.tool_name or "tool",
                            event.summary,
                            event.approval,
                        )
            return text

        try:
            run = await TaskRunner().run_isolated(TaskSpec(objective), self.worktree_manager, worker, keep_worktree=True)
            self.task_runs.append(run)
            chat_area.add_system_message(f"Isolated task {run.id[:8]} {run.status}: {run.result}\nDiff:\n{run.diff or '(no changes)'}")
        finally:
            self.execution_gateway = original_gateway

    async def _plan_steps(self, objective: str, previous: list[PlanStep]) -> list[PlanStep]:
        response = await self.llm_client.chat([
            Message(MessageRole.SYSTEM, "Break the objective into 2-5 executable coding steps. Return only a JSON array of strings. When prior steps failed, replace only the remaining work."),
            Message(MessageRole.USER, f"Objective: {objective}\nPrior steps: {[(item.objective, item.status, item.error) for item in previous]}"),
        ])
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        items = json.loads(raw)
        if not isinstance(items, list) or not all(isinstance(item, str) and item.strip() for item in items):
            raise ValueError("Planner did not return a JSON array of steps")
        return [PlanStep(item.strip()) for item in items[:5]]

    async def _run_subagent(self, objective: str, role: str = "executor", board: str = "") -> str:
        manager = ConversationManager()
        manager.create_conversation()
        manager.add_message(Message(MessageRole.USER, objective))
        text = ""
        async for event in run_agent_loop(
            llm_client=self.llm_client,
            conversation_manager=manager,
            tool_registry=self.tool_registry,
            tools_payload=self._build_tools_payload(),
            build_messages=lambda: [
                Message(MessageRole.SYSTEM, build_system_prompt(self.tool_context, self.tool_registry)),
                Message(MessageRole.SYSTEM, f"You are the {role} agent. Shared board:\n{board}"),
            ] + manager.get_messages(),
            execution_gateway=self.execution_gateway,
            context_budget=self.project_runtime.context_budget,
        ):
            if event.event_type == AgentEventType.STREAM_TEXT:
                text += event.text
            elif event.event_type == AgentEventType.APPROVAL_REQUIRED and event.request_id:
                self._show_approval_dialog(event.request_id, event.tool_name or "tool", event.summary, event.approval)
        if not text:
            text = manager.get_messages()[-1].content if manager.get_messages() else "No result"
        return text

    async def _run_planned_task(self, objective: str) -> None:
        chat_area = self.query_one("#chat-area", ChatArea)
        self.is_processing = True
        try:
            if not self._ensure_llm_client():
                return
            plan = await PlanExecutor(max_replans=1).run(
                objective,
                self._plan_steps,
                lambda step, steps: self._run_subagent(step.objective, "executor", "\n".join(item.objective for item in steps)),
            )
            lines = [f"{item.status}: {item.objective}" for item in plan.steps]
            chat_area.add_system_message("Plan completed" + f" (replans: {plan.replans}):\n" + "\n".join(lines))
        except Exception as exc:
            chat_area.add_system_message(f"Plan failed: {exc}")
        finally:
            self.is_processing = False

    async def _run_team_task(self, objective: str) -> None:
        chat_area = self.query_one("#chat-area", ChatArea)
        self.is_processing = True
        try:
            if not self._ensure_llm_client():
                return
            assignments = [
                AgentAssignment("researcher", f"Inspect the project and identify relevant files for: {objective}"),
                AgentAssignment("implementer", f"Implement the requested change: {objective}"),
            ]
            async def worker(assignment, board):
                return await self._run_subagent(assignment.objective, assignment.role, board.summary())
            async def reviewer(board):
                return await self._run_subagent(
                    "Review the implementation against the objective. Inspect changed files and run relevant tests. "
                    "List concrete issues. End the response with exactly `VERDICT: PASS` only when tests pass and no blocking issue remains; otherwise end with `VERDICT: FIX`.",
                    "reviewer",
                    board.summary(),
                )
            board = await CollaborativeRunner(max_concurrency=1).run(objective, assignments, worker, reviewer)
            if not review_passed(board.review):
                repair = await self._run_subagent(
                    "Fix every blocking issue reported by the reviewer, then run the relevant tests.",
                    "repairer",
                    board.summary() + "\n\nReviewer report:\n" + board.review,
                )
                board.entries.append(type(board.entries[0])("repairer", "Fix reviewer findings", repair, "completed"))
                board.verification = await self._run_subagent(
                    "Verify the final implementation independently. Inspect the changes and run relevant tests. "
                    "End with exactly `VERDICT: PASS` only if the task is complete and tests pass; otherwise end with `VERDICT: FIX`.",
                    "verifier",
                    board.summary(),
                )
            else:
                board.verification = board.review
            status = "accepted" if review_passed(board.verification) else "not accepted"
            chat_area.add_system_message(
                f"Team {status}.\n\nReview:\n{board.review}\n\nVerification:\n{board.verification}\n\nBoard:\n{board.summary()}"
            )
        except Exception as exc:
            chat_area.add_system_message(f"Team failed: {exc}")
        finally:
            self.is_processing = False

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

        routing = (self.config.get("agent") or {}).get("routing") or {}
        decision = classify_intent(content, int(routing.get("complexity_threshold", 3)))
        if routing.get("auto_plan", True) and decision.mode == "plan_execute":
            chat_area.add_system_message(
                "Complex coding request detected; switching to Plan-and-Execute."
            )
            self.run_worker(self._run_planned_task(content), exclusive=True)
            return

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
        user_messages = [message.content for message in self.conversation_manager.get_messages() if message.role is MessageRole.USER]
        retrieved = (
            self.memory_store.relevant_vector(self._memory_query_vector, user_messages[-1], limit=8)
            if self._memory_query_vector is not None and user_messages
            else self.memory_store.relevant(user_messages[-1] if user_messages else "", limit=8)
        )
        memories = [
            Message(MessageRole.SYSTEM, f"Project memory ({record.kind}): {record.content}")
            for record in retrieved
        ]
        skills = [
            Message(MessageRole.SYSTEM, f"Project skill ({item.source}): {item.content}")
            for item in self.skill_runner.context_items(self.skill_store.list())
        ]
        return [sys_msg] + skills + memories + self.conversation_manager.get_messages()

    def _context_summary(self) -> str:
        messages = self._messages_with_system()
        items = [ContextItem(message.role.value, message.content, index, max(1, len(message.content) // 4)) for index, message in enumerate(messages)]
        plan = plan_context(items, self.project_runtime.context_budget)
        return f"Context: {plan.used_tokens}/{plan.budget} tokens; included {len(plan.included)}, excluded {len(plan.excluded)}."

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

            embedding_config = ((self.config.get("memory") or {}).get("embedding") or {})
            vectors = await embed_with_provider([content], embedding_config)
            self._memory_query_vector = vectors[0] if vectors else None

            tool_widgets: dict[str, str] = {}
            is_streaming = False

            async for event in run_agent_loop(
                llm_client=self.llm_client,
                conversation_manager=self.conversation_manager,
                tool_registry=self.tool_registry,
                tools_payload=self._build_tools_payload(),
                build_messages=self._messages_with_system,
                cancel_event=self._agent_cancel_event,
                execution_gateway=self.execution_gateway,
                context_budget=self.project_runtime.context_budget,
                hook_runner=self.hook_runner,
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

                elif event.event_type == AgentEventType.APPROVAL_REQUIRED:
                    chat_area.add_approval_request(
                        event.request_id or "unknown",
                        event.tool_name or "tool",
                        event.summary,
                        event.approval,
                    )
                    if event.request_id:
                        self._show_approval_dialog(
                            event.request_id,
                            event.tool_name or "tool",
                            event.summary,
                            event.approval,
                        )
                    status_bar.update_agent_status("Approval required")

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
            await self._extract_memories(content)

        except Exception as e:
            logger.error("Error in LLM processing: %s", e, exc_info=True)
            chat_area.add_system_message(f"Error: {e}")
            status_bar.update_agent_status("Error")

        finally:
            self.is_processing = False
            self._agent_cancel_event = None
            self._memory_query_vector = None
            logger.info("is_processing set to False")

    async def _extract_memories(self, task: str) -> None:
        """Persist stable project facts extracted from a completed interaction."""
        memory_config = self.config.get("memory") or {}
        if not memory_config.get("auto_extract", True) or self.llm_client is None or not hasattr(self.llm_client, "chat"):
            return
        try:
            transcript = "\n".join(
                f"{message.role.value}: {message.content[:1200]}"
                for message in self.conversation_manager.get_messages()[-12:]
            )
            response = await self.llm_client.chat([
                Message(MessageRole.SYSTEM, "Extract only durable project facts, conventions, or decisions. Return JSON array objects with content, kind, and confidence (0-1). Return [] for no durable facts. Do not include secrets."),
                Message(MessageRole.USER, f"Task: {task}\n\nOutcome and tool evidence:\n{transcript}"),
            ])
            raw = response.content.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            facts = json.loads(raw)
            if not isinstance(facts, list):
                return
            existing = {item.content for item in self.memory_store.list()}
            candidates = []
            for fact in facts[:5]:
                if not isinstance(fact, dict):
                    continue
                value = fact.get("content")
                confidence = fact.get("confidence", 0)
                if isinstance(value, str) and 4 <= len(value.strip()) <= 300 and value not in existing and isinstance(confidence, (int, float)) and confidence >= 0.5:
                    candidates.append(MemoryRecord(value.strip(), kind=str(fact.get("kind", "fact"))[:40], source="auto", confidence=float(confidence), status="pending"))
            vectors = await embed_with_provider([item.content for item in candidates], memory_config.get("embedding") or {})
            for index, record in enumerate(candidates):
                if vectors is not None:
                    record.vector = vectors[index]
                self.memory_store.save(record)
        except Exception as exc:  # memory extraction must never fail the task
            logger.debug("Automatic memory extraction skipped: %s", exc)

    def action_cancel_agent(self) -> None:
        """Cancel the active agent loop without quitting the app."""
        if self.is_processing and self._agent_cancel_event is not None:
            self._agent_cancel_event.set()
            if self.execution_gateway is not None:
                self.execution_gateway.cancel_pending()
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
