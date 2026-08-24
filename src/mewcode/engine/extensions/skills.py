"""Skill instructions become explicit, source-labelled context items."""

from dataclasses import dataclass

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
