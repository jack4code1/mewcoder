"""Registered slash-command definitions, independent of TUI dispatch."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandDefinition:
    name: str
    description: str
    enabled: bool = True


DEFAULT_COMMANDS = (
    CommandDefinition("/help", "Show available commands"),
    CommandDefinition("/copy", "Copy the last reply"),
    CommandDefinition("/clear", "Clear the chat"),
    CommandDefinition("/save", "Save the session"),
    CommandDefinition("/sessions", "List saved sessions"),
    CommandDefinition("/resume", "Resume a saved session by ID"),
    CommandDefinition("/mode", "Toggle mode"),
    CommandDefinition("/quit", "Quit MewCode"),
    CommandDefinition("/audit", "Show recent security audit entries"),
    CommandDefinition("/context", "Show current context budget"),
    CommandDefinition("/memory", "List project memory"),
    CommandDefinition("/remember", "Save project memory"),
    CommandDefinition("/forget", "Delete project memory"),
    CommandDefinition("/skills", "List active project skills"),
    CommandDefinition("/skill add", "Create a project Skill"),
    CommandDefinition("/skill delete", "Delete a project Skill"),
    CommandDefinition("/memory search", "Search project memory"),
    CommandDefinition("/memory review", "Review automatic memory candidates"),
    CommandDefinition("/memory approve", "Approve a memory candidate"),
    CommandDefinition("/memory reject", "Reject a memory candidate"),
    CommandDefinition("/summarize", "Summarize earlier conversation context"),
    CommandDefinition("/task", "Run a read-only isolated task"),
    CommandDefinition("/plan", "Plan, execute, and recover a task"),
    CommandDefinition("/team", "Run collaborating role-based agents"),
    CommandDefinition("/tasks", "Show isolated task results"),
    CommandDefinition("/task apply", "Apply an isolated task diff"),
    CommandDefinition("/task discard", "Discard an isolated task"),
    CommandDefinition("/mcp", "Show configured MCP servers"),
    CommandDefinition("/mcp connect", "Connect a configured MCP server"),
    CommandDefinition("/approve", "Approve a tool for this session"),
    CommandDefinition("/approve project", "Approve a tool for this project"),
    CommandDefinition("/approve-request", "Approve a pending request"),
    CommandDefinition("/approve-project-request", "Approve a request for this project"),
    CommandDefinition("/deny", "Revoke a tool approval"),
    CommandDefinition("/deny project", "Revoke a project tool approval"),
    CommandDefinition("/deny-request", "Deny a pending request"),
)


class CommandCatalog:
    def __init__(self, commands: tuple[CommandDefinition, ...] = DEFAULT_COMMANDS) -> None:
        self._commands = {command.name: command for command in commands}

    def names(self) -> list[str]:
        return [command.name for command in self._commands.values() if command.enabled]

    def definitions(self) -> list[CommandDefinition]:
        return [command for command in self._commands.values() if command.enabled]

    def get(self, name: str) -> CommandDefinition | None:
        command = self._commands.get(name)
        return command if command and command.enabled else None
