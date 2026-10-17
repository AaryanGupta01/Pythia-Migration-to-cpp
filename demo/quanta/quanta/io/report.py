"""Plain-text report rendering for suite results."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Section:
    """A titled block of 'label: value' lines."""

    title: str
    lines: List[str] = field(default_factory=list)

    def add(self, label: str, value: Any) -> None:
        if isinstance(value, float):
            value = "%.6g" % value
        self.lines.append("%-24s %s" % (label + ":", value))


class Report:
    """Collects sections and emits them in insertion order; also exposes the raw numbers for JSON."""

    def __init__(self, title: str) -> None:
        self.title = title
        self.sections: List[Section] = []
        self.data: Dict[str, Any] = {}

    def section(self, title: str) -> Section:
        sec = Section(title)
        self.sections.append(sec)
        self.data[title] = {}
        return sec

    def record(self, section: Section, label: str, value: Any) -> None:
        section.add(label, value)
        self.data[section.title][label] = value

    def render(self) -> str:
        out = [self.title, "=" * len(self.title)]
        for sec in self.sections:
            out.append("")
            out.append("[%s]" % sec.title)
            out.extend(sec.lines)
        return "\n".join(out)


def format_table(headers: List[str], rows: List[List[Any]]) -> str:
    """Left-aligned text table with a header rule."""
    cells = [[("%.4g" % c if isinstance(c, float) else str(c)) for c in row] for row in rows]
    widths = [max([len(h)] + [len(r[i]) for r in cells]) for i, h in enumerate(headers)]
    lines = ["  ".join(h.ljust(w) for h, w in zip(headers, widths)),
             "  ".join("-" * w for w in widths)]
    for r in cells:
        lines.append("  ".join(c.ljust(w) for c, w in zip(r, widths)))
    return "\n".join(lines)


def bar(value: float, scale: float, width: int = 30) -> str:
    """Horizontal bar made of '#' characters, `width` wide at value == scale."""
    n = int(round(width * value / scale)) if scale > 0 else 0
    return "#" * max(0, min(width, n))
