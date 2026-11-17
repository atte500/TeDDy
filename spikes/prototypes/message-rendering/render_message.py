"""Spike: preview how a `## Message` body renders with `rich.markdown`.

`ConsoleInteractor.display_message` prints the body verbatim to stderr today.
This spike renders the same body three ways and measures the trade-offs that
decide the slice:

* does a fenced block survive byte-for-byte (a handoff command must stay
  copy-pasteable);
* does rich crop a line longer than the console width;
* do box-drawing characters leak into the fenced region;
* how much taller does the body get at 80 and 100 columns.

Run from the project root:

    uv run python spikes/prototypes/message-rendering/render_message.py

Generated artifacts land in `.tmp/message-rendering/` for a colour preview.
"""

from __future__ import annotations

import io
from importlib.metadata import version as package_version
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown

OUT_DIR = Path(".tmp/message-rendering")
BOX_CHARS = set("│┃╭╮╰╯─┌┐└┘├┤┬┴┼━┏┓┗┛┣┫┳┻╋")

HANDOFF = (
    "teddy start -a developer -m 'Render the Message body with rich.markdown "
    "behind a stderr TTY check and keep redirects raw' -c "
    "'docs/project/specs/interactive-session-workflow.md'"
)

BODY = f"""\
Both pieces are feasible. Here is what I found and what I recommend.

**Formatted rendering — yes, cheap.** The Message body goes to stderr today, so
`--pipeline` stdout stays machine-readable no matter how we render it.

What changes on screen:

- Headings stop showing `##` markers.
- Bullets render with a glyph and a hanging indent.
- Inline code sits on a subtle background.
- Fenced blocks keep their exact bytes, so handoffs stay copy-pasteable.

Handoff example:

```bash
{HANDOFF}
```

| Option | Scope | Cost |
| :----- | :---- | :--- |
| Rendering | one adapter | none |
| Auto-staging | new outbound port | mutates your index |

TL;DR: rendering is a contained adapter change; staging needs a git port.
"""


def render_rich(body: str, *, width: int = 100, soft_wrap: bool = False) -> str:
    buffer = io.StringIO()
    console = Console(
        file=buffer,
        width=width,
        record=True,
        force_terminal=True,
        soft_wrap=soft_wrap,
    )
    console.print(Markdown(body))
    return console.export_text()


def fence_probe(text: str) -> str:
    if HANDOFF not in text:
        return "handoff line missing or cropped"
    lines = text.splitlines()
    idx = next(i for i, line in enumerate(lines) if HANDOFF in line)
    window = lines[max(0, idx - 1) : idx + 2]
    box = sorted({char for line in window for char in line if char in BOX_CHARS})
    return f"fence window box chars: {box if box else 'none'}"


def report(label: str, text: str) -> None:
    print(label)
    print(f"  lines={len(text.splitlines())} chars={len(text)}")
    print(f"  handoff preserved: {HANDOFF in text}")
    print(f"  ellipsis crop: {'…' in text}")
    print(f"  bold markers left: {'**' in text}")
    print(f"  {fence_probe(text)}")
    print()


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    variants = {
        "raw-today": BODY,
        "rich-width-100": render_rich(BODY, width=100),
        "rich-width-80": render_rich(BODY, width=80),
        "rich-width-100-softwrap": render_rich(BODY, width=100, soft_wrap=True),
    }

    print(f"rich {package_version('rich')}\n")
    for label, text in variants.items():
        report(label, text)

    for name, text in variants.items():
        (OUT_DIR / f"{name}.txt").write_text(text, encoding="utf-8")

    console = Console(record=True, width=100, file=io.StringIO())
    console.print(Markdown(BODY))
    console.save_svg(str(OUT_DIR / "message.svg"), title="Message rendering preview")
    console.save_html(str(OUT_DIR / "message.html"))

    print("--- rich width=100, plain-text layout ---")
    print(variants["rich-width-100"])
    print(f"artifacts: {OUT_DIR}/message.svg, {OUT_DIR}/message.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
