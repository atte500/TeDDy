"""Spike: show what "rewritten" and "split" look like for tilde fences.

The slice originally told the Developer to re-emit every fenced block with
synthesized three-backtick delimiters. That is wrong in two visible ways:

* rewritten -- a block opened with ``~~~`` comes back opened with ````` ```;
* split     -- a tilde block may legally hold a line that STARTS with a
               backtick run, and once the opener is synthesized as backticks
               that content line closes the block, so one fence becomes two and
               the rest of the block falls out as prose.

Counting defects is abstract. This spike annotates every line of the source,
the synthesized rendering, and the verbatim rendering with the role the fence
grammar assigns to it, so the two defects are read off the output directly.

Strategies:

    current   synthesized three-backtick delimiters (the rejected draft)
    verbatim  the segment's own opening and closing lines (the accepted draft)

Run from the project root:

    uv run python spikes/prototypes/message-rendering/show_tilde_rewrite.py

Nothing is written to disk, and no styling is emitted, so the output survives
piping and redirection unchanged.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.text import Text

try:
    from teddy_executor.core.utils.markdown import _FENCE_RE as FENCE_RE

    GRAMMAR = "production _FENCE_RE"
except Exception as exc:  # pragma: no cover - fallback for a bare checkout
    FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
    GRAMMAR = f"local copy ({type(exc).__name__}: {exc})"

WIDTH = 100


@dataclass(frozen=True)
class Segment:
    kind: str
    info: str
    content: str
    opening: str = ""
    closing: str = ""


def split(body: str) -> list[Segment]:
    """Split a body into prose and fence segments, keeping raw delimiter lines."""
    lines = body.split("\n")
    segments: list[Segment] = []
    prose: list[str] = []
    index = 0
    while index < len(lines):
        match = FENCE_RE.match(lines[index])
        if match is None:
            prose.append(lines[index])
            index += 1
            continue
        if prose and any(line.strip() for line in prose):
            segments.append(Segment("prose", "", "\n".join(prose)))
        prose = []
        fence = match.group(1)
        info = match.group(2).strip()
        code: list[str] = []
        closing = ""
        cursor = index + 1
        while cursor < len(lines):
            candidate = FENCE_RE.match(lines[cursor])
            if (
                candidate is not None
                and candidate.group(1)[0] == fence[0]
                and len(candidate.group(1)) >= len(fence)
                and not candidate.group(2).strip()
            ):
                closing = lines[cursor]
                break
            code.append(lines[cursor])
            cursor += 1
        segments.append(Segment("fence", info, "\n".join(code), lines[index], closing))
        index = cursor + 1
    if prose and any(line.strip() for line in prose):
        segments.append(Segment("prose", "", "\n".join(prose)))
    return segments


def _syntax(segment: Segment) -> Syntax:
    return Syntax(
        segment.content,
        segment.info or "text",
        word_wrap=False,
        padding=(0, 0),
        background_color="default",
    )


def render(body: str, style: str, width: int = WIDTH) -> str:
    """Render ``body`` with delimiters either synthesized or re-emitted."""
    parts: list[str] = []
    for segment in split(body):
        buffer = io.StringIO()
        if segment.kind == "prose":
            Console(file=buffer, width=width, force_terminal=False).print(
                Markdown(segment.content)
            )
            parts.append(buffer.getvalue())
            continue
        longest = max((len(line) for line in segment.content.split("\n")), default=0)
        console = Console(file=buffer, width=max(width, longest), force_terminal=False)
        if style == "current":
            console.print(Text(f"```{segment.info}", style="dim"))
            console.print(_syntax(segment))
            console.print(Text("```", style="dim"))
        else:
            console.print(Text(segment.opening, style="dim"))
            console.print(_syntax(segment))
            if segment.closing:
                console.print(Text(segment.closing, style="dim"))
        parts.append(buffer.getvalue())
    return "".join(parts)


def annotate(text: str) -> list[tuple[str, str]]:
    """Return (line, role) pairs, where role is the grammar's reading of it."""
    lines = text.rstrip("\n").split("\n")
    roles = ["prose"] * len(lines)
    open_char: str | None = None
    open_len = 0
    open_line: int | None = None
    for index, line in enumerate(lines):
        match = FENCE_RE.match(line)
        if match is not None:
            fence = match.group(1)
            info = match.group(2)
            if open_char is None:
                roles[index] = "opener"
                open_char = fence[0]
                open_len = len(fence)
                open_line = index
                continue
            if fence[0] == open_char and len(fence) >= open_len and not info.strip():
                roles[index] = "closer"
                open_char = None
                open_len = 0
                open_line = None
                continue
            roles[index] = "fence content"
            continue
        roles[index] = "prose" if open_char is None else "fence content"
    if open_char is not None and open_line is not None:
        roles[open_line] = "opener (never closed)"
    return list(zip(lines, roles, strict=True))


def show(label: str, text: str) -> None:
    print(f"  {label}")
    for number, (line, role) in enumerate(annotate(text), start=1):
        print(f"    {number:2d} | {line}   [{role}]")
    print()


def delimiters(text: str) -> list[str]:
    return [s.opening.lstrip()[:1] or "?" for s in split(text) if s.kind == "fence"]


def verdict(source: str, rendered: str, style: str) -> str:
    source_delims = delimiters(source)
    rendered_delims = delimiters(rendered)
    problems: list[str] = []
    if len(rendered_delims) != len(source_delims):
        problems.append(f"fence count {len(source_delims)} -> {len(rendered_delims)}")
    if rendered_delims != source_delims:
        problems.append(f"delimiters {source_delims} -> {rendered_delims}")
    if not problems:
        return "intact: same fence count and same delimiter characters"
    return "DEFECT: " + "; ".join(problems)


SCENARIOS: dict[str, str] = {
    "tilde block holding a backtick run": (
        "Prose before the block.\n\n"
        "~~~\n"
        "```\n"
        "a backtick run at the start of a line, legal inside a tilde fence\n"
        "~~~\n\n"
        "Prose after the block.\n"
    ),
    "two tilde blocks in one body": (
        "Prose before.\n\n"
        "~~~bash\n"
        "uv run teddy resume -p --session 20261117-message-rendering-preview\n"
        "~~~\n\n"
        "Prose between.\n\n"
        "~~~~python\n"
        "def f():\n"
        '    return "```"\n'
        "~~~~\n\n"
        "Prose after.\n"
    ),
}


def main() -> int:
    print(f"fence grammar: {GRAMMAR}")
    print(f"pattern: {FENCE_RE.pattern}")
    print(f"render width: {WIDTH}")
    print()

    for title, body in SCENARIOS.items():
        print("=" * 78)
        print(f"BODY: {title}")
        print("=" * 78)
        show("source", body)

        for style in ("current", "verbatim"):
            rendered = render(body, style)
            label = (
                "current -- delimiters synthesized as three backticks"
                if style == "current"
                else "verbatim -- the segment's own opening and closing lines"
            )
            print(f"--- {label} ---")
            show("rendered output, annotated by the fence grammar", rendered)
            print(f"  {verdict(body, rendered, style)}")
            print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
