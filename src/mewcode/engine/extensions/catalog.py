from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass(frozen=True)
class ExtensionDefinition:
    name: str
    kind: str
    description: str = ""
    enabled: bool = True
    source: str = ""


class ExtensionCatalog:
    def __init__(self) -> None:
        self.items: dict[str, ExtensionDefinition] = {}
        self.errors: list[str] = []

    def load(self, directory: Path) -> None:
        if not directory.exists():
            return
        for path in directory.glob("*.yaml"):
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                item = ExtensionDefinition(source=str(path), **raw)
                if item.name in self.items:
                    raise ValueError(f"duplicate extension: {item.name}")
                self.items[item.name] = item
            except Exception as exc:
                self.errors.append(f"{path.name}: {exc}")

    def enabled(self, kind: str | None = None) -> list[ExtensionDefinition]:
        return [item for item in self.items.values() if item.enabled and (kind is None or item.kind == kind)]
