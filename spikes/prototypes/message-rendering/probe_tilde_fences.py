"""Probe: does the segmented renderer survive tilde fences?

CommonMark accepts a tilde run as a fence delimiter, and the project's grammar
already does too. The slice drafts its delimiters as literal backticks, so a
tilde block comes back as a backtick block — harmless until the tilde block
holds a line that STARTS with a backtick run, at which point the re-emitted
opener is closed by that content line and the block shatters.

This probe renders five bodies through three delimiter strategies and reports,
per combination, the fence count before and after, the opening delimiter
character before and after, and whether every source content line survives
verbatim.

Strategies:

    current   delimiters synthesized as three backticks (the slice as drafted)
    verbatim  delimiters re-emitted from the segment's own source lines
    none      no delimiters at all, the bare-fence treatment

Run from the project root:

    uv run python spikes/prototypes/message-rendering/probe_tilde_fences.py
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
    from teddy_executor.core.utils.markdown import strip_trailing_open_fence

    GRAMMAR = "production _FENCE_RE"
except Exception as exc:  # pragma: no cover - fallback for a bare checkout
    FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
    strip_trailing_open_fence = None
    GRAMMAR = f"local copy ({type(exc).__name__}: {exc})"

WIDTH = 100
LONG = (
    "teddy start -a developer -m 'Render the Message body with syntax colours "
    "and dim fence lines' -c 'docs/project/slices/00-20-message-body-rendering.md'"
)


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
        if prose:
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
        segments.append(
            Segment("fence", info, "\n".join(code), lines[index], closing)
        )
        index = cursor + 1
    if prose:
        segments.append(Segment("prose", "", "\n".join(prose)))
    return segments


def _console(buffer: io.StringIO, width: int) -> Console:
    return Console(file=buffer, width=width, force_terminal=False)


def _syntax(segment: Segment) -> Syntax:
    return Syntax(
        segment.content,
        segment.info or "text",
        word_wrap=False,
        padding=(0, 0),
        background_color="default",
    )


def _render_prose(text: str, width: int) -> str:
    buffer = io.StringIO()
    _console(buffer, width).print(Markdown(text))
    return buffer.getvalue()


def _render_fence(segment: Segment, style: str, width: int) -> str:
    longest = max((len(line) for line in segment.content.split("\n")), default=0)
    buffer = io.StringIO()
    console = _console(buffer, max(width, longest))
    if style == "current":
        console.print(Text(f"```{segment.info}", style="dim"))
        console.print(_syntax(segment))
        console.print(Text("```", style="dim"))
    elif style == "verbatim":
        console.print(Text(segment.opening, style="dim"))
        console.print(_syntax(segment))
        if segment.closing:
            console.print(Text(segment.closing, style="dim"))
    else:
        console.print(_syntax(segment))
    return buffer.getvalue()


def render(body: str, style: str, width: int = WIDTH) -> str:
    return "".join(
        _render_prose(segment.content, width)
        if segment.kind == "prose"
        else _render_fence(segment, style, width)
        for segment in split(body)
    )


def delim(line: str) -> str:
    stripped = line.lstrip()
    return stripped[:1] if stripped else ""


def summarize(name: str, body: str, style: str) -> str:
    rendered = render(body, style)
    source_fences = [s for s in split(body) if s.kind == "fence"]
    rendered_fences = [s for s in split(rendered) if s.kind == "fence"]
    rendered_lines = {line.rstrip() for line in rendered.split("\n")}
    intact = all(
        line.rstrip() in rendered_lines
        for segment in source_fences
        for line in segment.content.split("\n")
        if line.strip()
    )
    return (
        f"{name:22s} {style:9s} "
        f"fences={len(source_fences)}->{len(rendered_fences)} "
        f"chars={[delim(s.opening) for s in source_fences]}"
        f"->{[delim(s.opening) for s in rendered_fences]} "
        f"intact={intact}"
    )


def markdown_fallback(name: str, body: str) -> None:
    buffer = io.StringIO()
    _console(buffer, WIDTH).print(Markdown(body))
    text = buffer.getvalue()
    print(
        f"  {name:22s} tilde_markers_left={'~~~' in text} "
        f"non_empty_lines={sum(1 for line in text.splitlines() if line.strip())}"
    )


def check_strip() -> None:
    if strip_trailing_open_fence is None:
        print("\nstrip_trailing_open_fence: unavailable")
        return
    unclosed = "prose\n~~~bash\necho hi"
    balanced = "~~~bash\necho hi\n~~~\ntail"
    print(
        "\nstrip_trailing_open_fence, unclosed tilde fence: "
        f"{'opener removed' if '~~~' not in strip_trailing_open_fence(unclosed) else 'OPENER KEPT'}"
    )
    print(
        "strip_trailing_open_fence, balanced tilde fence: "
        f"{'unchanged' if strip_trailing_open_fence(balanced) == balanced else 'MODIFIED'}"
    )


BODIES: dict[str, str] = {
    "mixed": (
        "Intro prose with a `code` span.\n\n"
        f"~~~bash\n{LONG}\n~~~\n\n"
        "Between blocks.\n\n"
        "~~~~python\n"
        "def f():\n"
        '    return "```"\n'
        "~~~~\n"
    ),
    "tilde-holding-backticks": (
        "~~~\n"
        "```\n"
        "a backtick run at the start of a line, legal inside a tilde fence\n"
        "~~~\n"
    ),
    "indented": (
        "   ~~~json\n"
        '   {"session": "20261117-message-rendering"}\n'
        "   ~~~\n"
    ),
    "unclosed": "prose before\n\n~~~bash\necho still inside the block\n",
    "longer-closing-run": (
        "~~~\n" "short opening, longer closing run\n" "~~~~~\n"
    ),
}


def main() -> int:
    print(f"fence grammar: {GRAMMAR}")
    print(f"pattern: {FENCE_RE.pattern}")
    print(f"width: {WIDTH}\n")

    for name, body in BODIES.items():
        print(f"[{name}]")
        for style in ("current", "verbatim", "none"):
            print("  " + summarize(name, body, style))
        print()

    print("Markdown fallback, if the splitter ever misses a tilde fence:")
    for name in ("mixed", "tilde-holding-backticks"):
        markdown_fallback(name, BODIES[name])

    check_strip()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
