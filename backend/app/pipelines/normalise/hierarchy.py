"""Incremental heading path and structural hierarchy state."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HierarchyState:
    """Mutable single-pass hierarchy cursor."""

    heading_stack: list[tuple[int, str]] = field(default_factory=list)
    # stack entries: (level, title)

    def update_heading(self, level: int | None, title: str) -> list[str]:
        """Push/pop heading stack; return the new heading_path copy."""
        lvl = level if level is not None and level > 0 else (
            (self.heading_stack[-1][0] + 1) if self.heading_stack else 1
        )
        # Pop deeper or equal levels
        while self.heading_stack and self.heading_stack[-1][0] >= lvl:
            self.heading_stack.pop()
        self.heading_stack.append((lvl, title))
        return self.path()

    def path(self) -> list[str]:
        return [title for _, title in self.heading_stack]

    def replace_root(self, titles: list[str]) -> list[str]:
        """Force a path prefix (e.g. after opening a part/chapter)."""
        self.heading_stack = [(i + 1, t) for i, t in enumerate(titles)]
        return self.path()
