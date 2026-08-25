"""Skill instructions become explicit, source-labelled context items."""

from dataclasses import dataclass
from pathlib import Path
import re

from ..context import ContextItem


@dataclass(frozen=True)
class SkillDefinition:
    name: str
    instructions: str
    enabled: bool = True
    source: str = "project"


class SkillRunner:
    def context_items(self, skills: list[SkillDefinition]) -> list[ContextItem]:
        return [
            ContextItem(f"skill:{skill.name}", skill.instructions, priority=80,
                        token_estimate=max(1, len(skill.instructions) // 4))
            for skill in skills if skill.enabled
        ]


class ProjectSkillStore:
    """Discover project-local Markdown skills without a separate manifest."""

    def __init__(self, workspace: Path) -> None:
        self.path = workspace.resolve() / ".mewcode" / "skills"

    def list(self) -> list[SkillDefinition]:
        if not self.path.is_dir():
            return []
        skills = []
        for file_path in sorted(self.path.glob("*.md")):
            content = file_path.read_text(encoding="utf-8").strip()
            if content:
                skills.append(SkillDefinition(file_path.stem, content, source=str(file_path)))
        return skills

    def save(self, name: str, instructions: str) -> SkillDefinition:
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name):
            raise ValueError("Skill name must use lowercase letters, numbers, hyphens, or underscores.")
        content = instructions.strip()
        if not content:
            raise ValueError("Skill instructions cannot be empty.")
        self.path.mkdir(parents=True, exist_ok=True)
        file_path = self.path / f"{name}.md"
        file_path.write_text(content + "\n", encoding="utf-8")
        return SkillDefinition(name, content, source=str(file_path))

    def delete(self, name: str) -> bool:
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name):
            return False
        path = self.path / f"{name}.md"
        if not path.exists():
            return False
        path.unlink()
        return True
