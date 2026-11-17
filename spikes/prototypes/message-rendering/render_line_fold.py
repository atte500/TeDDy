"""Spike: keep a fenced handoff command on ONE line while formatting the prose.

Earlier probes established three facts:

1. `overflow="ignore"` and `soft_wrap=True` on `Console.print` do NOT stop an
   over-long `Text` from being folded at the console width.
2. Only a console wider than the line keeps it intact.
3. A whole-body wide console pads prose to tens of thousands of characters,
   because Markdown aligns tables to the console width.

This probe (a) tests every remaining knob on a bare `Text` so a failure is
unambiguous, and (b) measures the fallback design: prose on a terminal-width
console, each fenced block on its own console sized to that block's longest
line.

Run from the project root:

    uv run python spikes/prototypes/message-rendering/render_line_fold.py
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.text import Text

OUT_DIR = Path(".tmp/message-rendering")
TERM_WIDTH = 100

LONG = (
    "teddy start -a developer -m 'Render the Message body' -c "
    "'docs/project/specs/interactive-session-workflow.md'"
)

HANDOFF = (
    "teddy start -a developer -m 'Render the Message body with rich.markdown "
    "behind a stderr TTY check and keep redirects raw' -c "
    "'docs/project/specs/interactive-session-workflow.md'"
)

BODY = (
    "Both pieces are feasible.\n\n"
    "**Formatted rendering — yes, cheap.** The body goes to stderr, so\n"
    "`--pipeline` stdout stays machine-readable.\n\n"
    "Handoff example:\n\n"
    "```bash\n" + HANDOFF + "\n```\n\n"
    "| Option | Scope | Cost |\n"
    "| :----- | :---- | :--- |\n"
    "| Rendering | one adapter | none |\n"
    "| Auto-staging | new outbound port | mutates your index |\n\n"
    "TL;DR: rendering is a contained adapter change.\n"
)

FENCE_RE = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")


def split_segments(body: str) -> list[tuple[str, str, str]]:
    """Split a Markdown body into ('prose', '', text) and ('fence', info, code)."""
    lines = body.split("\n")
    segments: list[tuple[str, str, str]] = []
    prose: list[str] = []
    index = 0
    while index < len(lines):
        match = FENCE_RE.match(lines[index])
        if match is None:
            prose.append(lines[index])
            index += 1
            continue
        if prose:
            segments.append(("prose", "", "\n".join(prose)))
            prose = []
        fence = match.group(2)
        info = match.group(3).strip()
        code: list[str] = []
        cursor = index + 1
        while cursor < len(lines):
            closing = FENCE_RE.match(lines[cursor])
            if (
                closing is not None
                and closing.group(2)[0] == fence[0]
                and len(closing.group(2)) >= len(fence)
                and not closing.group(3).strip()
            ):
                break
            code.append(lines[cursor])
            cursor += 1
        segments.append(("fence", info, "\n".join(code)))
        index = cursor + 1
    if prose:
        segments.append(("prose", "", "\n".join(prose)))
    return segments


def _render_bare(
    renderable: Text,
    *,
    width: int = 40,
    console_kwargs: dict[str, Any] | None = None,
    print_kwargs: dict[str, Any] | None = None,
) -> str:
    console = Console(
        file=io.StringIO(),
        width=width,
        force_terminal=True,
        record=True,
        **(console_kwargs or {}),
    )
    console.print(renderable, **(print_kwargs or {}))
    return console.export_text()


def knob_matrix() -> list[tuple[str, str]]:
    def case(
        *,
        console_kwargs: dict[str, Any] | None = None,
        print_kwargs: dict[str, Any] | None = None,
        **text_kwargs: Any,
    ) -> str:
        return _render_bare(
            Text(LONG, **text_kwargs),
            console_kwargs=console_kwargs,
            print_kwargs=print_kwargs,
        )

    return [
        ("bare/plain", case()),
        ("bare/overflow-ignore", case(print_kwargs={"overflow": "ignore"})),
        ("bare/crop-false", case(print_kwargs={"crop": False})),
        ("bare/soft-wrap-print", case(print_kwargs={"soft_wrap": True})),
        ("bare/no-wrap", case(no_wrap=True)),
        ("bare/no-wrap+crop-false", case(no_wrap=True, print_kwargs={"crop": False})),
        (
            "bare/ignore+crop-false",
            case(overflow="ignore", print_kwargs={"crop": False, "overflow": "ignore"}),
        ),
        ("bare/console-soft-wrap", case(console_kwargs={"soft_wrap": True})),
    ]


def render_message(body: str, term_width: int, strategy: str) -> str:
    """Prose on a terminal-width console; each fence on its own sized console."""
    parts: list[str] = []
    for kind, info, content in split_segments(body):
        buffer = io.StringIO()
        if kind == "prose":
            console = Console(
                file=buffer, width=term_width, force_terminal=True, record=True
            )
            console.print(Markdown(content))
        else:
            longest = max((len(line) for line in content.split("\n")), default=0)
            console = Console(
                file=buffer,
                width=max(term_width, longest),
                force_terminal=True,
                record=True,
            )
            if strategy == "syntax":
                console.print(
                    Syntax(content, info or "text", word_wrap=False, padding=(0, 0))
                )
            else:
                console.print(Text(content))
        parts.append(console.export_text())
    return "".join(parts)


def render_message_svg(path: Path, strategy: str, canvas_width: int) -> None:
    console = Console(
        file=io.StringIO(), width=canvas_width, force_terminal=True, record=True
    )
    for kind, info, content in split_segments(BODY):
        if kind == "prose":
            console.print(Markdown(content))
        elif strategy == "syntax":
            console.print(
                Syntax(content, info or "text", word_wrap=False, padding=(0, 0))
            )
        else:
            console.print(Text(content))
    console.save_svg(str(path), title=f"Message rendering — segmented/{strategy}")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(
        f"over-long line={len(LONG)} chars, bare console width=40, "
        f"body term width={TERM_WIDTH}\n"
    )

    print("--- knob matrix (bare Text) ---")
    for label, text in knob_matrix():
        intact = LONG in text
        print(f"{label:26s} intact={str(intact):5s} lines={len(text.splitlines())}")
        if not intact:
            print(f"    {text!r}")

    print("\n--- end-to-end segmented design ---")
    for width in (80, TERM_WIDTH):
        for strategy in ("syntax", "text"):
            text = render_message(BODY, width, strategy)
            intact = HANDOFF in text
            print(
                f"segmented/{strategy:6s} width={width:4d} "
                f"handoff_intact={str(intact):5s} "
                f"lines={len(text.splitlines()):3d} chars={len(text)}"
            )
            (OUT_DIR / f"segmented-{strategy}-w{width}.txt").write_text(
                text, encoding="utf-8"
            )

    canvas = max(TERM_WIDTH, max(len(line) for line in BODY.splitlines()))
    for strategy in ("syntax", "text"):
        render_message_svg(OUT_DIR / f"final-{strategy}.svg", strategy, canvas)
    print(f"\nSVG previews: {OUT_DIR}/final-syntax.svg, {OUT_DIR}/final-text.svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
