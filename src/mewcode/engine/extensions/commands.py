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
    CommandDefinition("/model", "Switch model"),
    CommandDefinition("/mode", "Toggle mode"),
    CommandDefinition("/quit", "Quit MewCode"),
    CommandDefinition("/audit", "Show recent security audit entries"),
    CommandDefinition("/context", "Show current context budget"),
    CommandDefinition("/memory", "List project memory"),
    CommandDefinition("/remember", "Save project memory"),
    CommandDefinition("/forget", "Delete project memory"),
)


class CommandCatalog:
    def __init__(self, commands: tuple[CommandDefinition, ...] = DEFAULT_COMMANDS) -> None:
        self._commands = {command.name: command for command in commands}

    def names(self) -> list[str]:
        return [command.name for command in self._commands.values() if command.enabled]

    def get(self, name: str) -> CommandDefinition | None:
        command = self._commands.get(name)
        return command if command and command.enabled else None
