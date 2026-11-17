"""Spike: find a fence-safe way to render a Message body with rich.

The first spike showed that a whole-body `rich.markdown.Markdown` render folds a
long fenced command at the console width, inserting newlines that break
copy-paste. This spike compares strategies that keep fenced blocks byte-exact
while still formatting the prose.

It answers one question: does `Console(overflow="ignore")` alone stop the fold,
or must the body be split into prose and fenced segments?

Run from the project root:

    uv run python spikes/prototypes/message-rendering/render_fence_safe.py
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

HANDOFF = (
    "teddy start -a developer -m 'Render the Message body with rich.markdown "
    "behind a stderr TTY check and keep redirects raw' -c "
    "'docs/project/specs/interactive-session-workflow.md'"
)

BODY = f"""\
Both pieces are feasible.

**Formatted rendering — yes, cheap.** The Message body goes to stderr, so
`--pipeline` stdout stays machine-readable.

Handoff example:

```bash
{HANDOFF}
```

| Option | Scope | Cost |
| :----- | :---- | :--- |
| Rendering | one adapter | none |

TL;DR: rendering is a contained adapter change.
"""

FENCE_RE = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")


def split_segments(body: str) -> list[tuple[str, str, str]]:
    """Split a Markdown body into ('prose', '', text) and ('fence', info, code)."""
    lines = body.split("\n")
    segments: list[tuple[str, str, str]] = []
    prose: list[str] = []
    i = 0
    while i < len(lines):
        match = FENCE_RE.match(lines[i])
        if match is None:
            prose.append(lines[i])
            i += 1
            continue
        if prose:
            segments.append(("prose", "", "\n".join(prose)))
            prose = []
        fence = match.group(2)
        info = match.group(3).strip()
        code: list[str] = []
        j = i + 1
        while j < len(lines):
            closing = FENCE_RE.match(lines[j])
            if (
                closing is not None
                and closing.group(2)[0] == fence[0]
                and len(closing.group(2)) >= len(fence)
                and not closing.group(3).strip()
            ):
                break
            code.append(lines[j])
            j += 1
        segments.append(("fence", info, "\n".join(code)))
        i = j + 1
    if prose:
        segments.append(("prose", "", "\n".join(prose)))
    return segments


def _recording_console(buffer: io.StringIO, width: int) -> Console:
    return Console(
        file=buffer, width=width, force_terminal=True, record=True
    )


def whole(body: str, width: int, **print_kwargs: Any) -> str:
    buffer = io.StringIO()
    console = _recording_console(buffer, width)
    console.print(Markdown(body), **print_kwargs)
    return console.export_text()


def whole_wide(body: str, width: int = 10_000) -> str:
    buffer = io.StringIO()
    console = _recording_console(buffer, width)
    console.print(Markdown(body))
    return console.export_text()


def render_segments(console: Console, body: str, fence_mode: str) -> None:
    for kind, info, content in split_segments(body):
        if kind == "prose":
            console.print(Markdown(content))
        elif fence_mode == "syntax":
            console.print(
                Syntax(content, info or "text", word_wrap=False, padding=(0, 0)),
                overflow="ignore",
            )
        elif fence_mode == "text":
            console.print(Text(content, no_wrap=True), overflow="ignore")
        else:
            console.print(Text(content, overflow="ignore"), overflow="ignore")


def segmented(body: str, width: int, fence_mode: str) -> str:
    buffer = io.StringIO()
    console = _recording_console(buffer, width)
    render_segments(console, body, fence_mode)
    return console.export_text()


def measure(label: str, text: str) -> None:
    preserved = HANDOFF in text
    leading_space = (" " + HANDOFF) in text
    lines = text.split("\n")
    index = next((i for i, line in enumerate(lines) if "teddy start" in line), None)
    print(
        f"{label:24s} handoff={str(preserved):5s} lead_space={str(leading_space):5s} "
        f"lines={len(lines):3d} chars={len(text)}"
    )
    if not preserved and index is not None:
        for window in lines[index : index + 3]:
            print(f"    |{window}")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    variants = {
        "whole/control": whole(BODY, 80),
        "whole/overflow-ignore": whole(BODY, 80, overflow="ignore"),
        "whole/softwrap": whole(BODY, 80, soft_wrap=True),
        "whole/wide-console": whole_wide(BODY),
        "seg/raw-fence": segmented(BODY, 80, "raw"),
        "seg/text-fence": segmented(BODY, 80, "text"),
        "seg/syntax-fence": segmented(BODY, 80, "syntax"),
    }
    for label, text in variants.items():
        measure(label, text)
    (OUT_DIR / "fence-safe-probe.txt").write_text(
        "\n\n".join(f"### {name}\n{text}" for name, text in variants.items()),
        encoding="utf-8",
    )

    for preview_label, mode in (
        ("seg/raw-fence", "raw"),
        ("seg/syntax-fence", "syntax"),
    ):
        console = Console(
            file=io.StringIO(), width=100, force_terminal=True, record=True
        )
        render_segments(console, BODY, mode)
        console.save_svg(
            str(OUT_DIR / f"preview-{preview_label.replace('/', '-')}.svg"),
            title=f"Message rendering — {preview_label}",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
