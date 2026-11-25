"""Proof: the render_lines/Segments replica keeps a Message reflowable.

The winning mechanism from the probe series: lay each prose block out at an
unbounded width (so Rich inserts no fold and crops nothing), trim the layout
padding, and re-emit each logical line through the real console so the
terminal owns the fold and can reflow it on resize. This validates the exact
sandbox replica (``replica_message_renderer.py``) that will become production.

Pass criteria at console widths 80 and 40:
1. Production output differs between widths, crops the second bullet at 40,
   and pads lines to the full console width (the defect, with data loss).
2. Replica output is byte-identical (terminal owns the fold).
3. Replica keeps the paragraph, both bullets, and the heading text whole.
4. Replica emits no trailing padding and exactly one blank line between blocks.
5. Replica keeps the fenced command byte-exact and strips prose markers.
6. On a terminal, replica keeps production's styles for bold and inline code,
   plus the dim fenced delimiters.
"""

from __future__ import annotations

import io
import pathlib
import re
import sys
from typing import Callable

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "spikes/debug/message-resize-reflow"))

from rich.console import Console

import replica_message_renderer
from teddy_executor.core.utils.message_renderer import (
    inline_code_theme,
    render_message_body,
)

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

PARAGRAPH = (
    "This is a deliberately long paragraph that a communicating turn would "
    "print as its Message body. It keeps going so that it clearly exceeds a "
    "narrow terminal width, forcing the renderer to choose between wrapping "
    "the text itself and leaving one logical line for the terminal to fold "
    "and reflow when the user resizes the window."
)

BULLET1 = "Bold should lose its asterisks."
BULLET1_RAW = "**Bold** should lose its asterisks."
BULLET2 = "Inline teddy resume -p should lose backticks."
BULLET2_RAW = "Inline `teddy resume -p` should lose backticks."

LONG_COMMAND = (
    "uv run teddy context -c README.md -c pyproject.toml "
    "-c docs/project/PROJECT.md --only"
)

BODY = f"""## Heads up

{PARAGRAPH}

- {BULLET1_RAW}
- {BULLET2_RAW}

```bash
echo before
{LONG_COMMAND}
echo after
```
"""


def _render(
    renderer: Callable[[str, Console], None], width: int, *, terminal: bool = False
) -> str:
    buffer = io.StringIO()
    console = Console(
        file=buffer,
        width=width,
        force_terminal=terminal,
        color_system="truecolor" if terminal else None,
        theme=inline_code_theme(),
    )
    renderer(BODY, console)
    return buffer.getvalue()


def _plain(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _style_run_before(text: str, needle: str) -> str:
    match = re.search(r"((?:\x1b\[[0-9;]*m)+)" + re.escape(needle), text)
    return match.group(1) if match else ""


def _dump(label: str, text: str) -> None:
    print(f"--- {label} ---")
    for i, line in enumerate(text.rstrip("\n").split("\n")):
        marker = "PAD" if line != line.rstrip() else "   "
        print(f"  [{i:02d}] {len(line):5d} {marker} | {line[:100]!r}")
    print()


def main() -> None:
    prod_80 = _render(render_message_body, 80)
    prod_40 = _render(render_message_body, 40)
    rep_80 = _render(replica_message_renderer.render_message_body, 80)
    rep_40 = _render(replica_message_renderer.render_message_body, 40)

    _dump("PRODUCTION @ width=80", prod_80)
    _dump("PRODUCTION @ width=40", prod_40)
    _dump("REPLICA @ width=40", rep_40)

    rep_lines = rep_80.split("\n")
    rep_plain = _plain(rep_80)
    padded_prod_lines = sum(1 for line in prod_80.split("\n") if line != line.rstrip())

    prod_ansi = _render(render_message_body, 80, terminal=True)
    rep_ansi = _render(replica_message_renderer.render_message_body, 80, terminal=True)
    bold_prod = _style_run_before(prod_ansi, "Bold")
    bold_rep = _style_run_before(rep_ansi, "Bold")
    code_prod = _style_run_before(prod_ansi, "teddy resume -p")
    code_rep = _style_run_before(rep_ansi, "teddy resume -p")

    checks = {
        "production output depends on width (defect)": prod_80 != prod_40,
        "production crops the second bullet at 40 (data loss)": BULLET2 not in prod_40,
        "production pads lines to the console width (defect)": padded_prod_lines >= 5,
        "replica output is width-invariant (terminal owns the fold)": rep_80 == rep_40,
        "replica keeps the paragraph whole at 80 and 40": PARAGRAPH in rep_80
        and PARAGRAPH in rep_40,
        "replica keeps both bullets whole at 80 and 40": all(
            needle in text for needle in (BULLET1, BULLET2) for text in (rep_80, rep_40)
        ),
        "replica renders the heading without hashes": "## Heads up" not in rep_plain
        and any(line == "Heads up" for line in rep_lines),
        "replica strips bold and inline-code markers": BULLET1_RAW not in rep_plain
        and "`teddy resume -p`" not in rep_plain,
        "replica emits no trailing padding": all(
            line == line.rstrip() for line in rep_lines
        ),
        "replica keeps one blank line between blocks": "\n\n\n" not in rep_80
        and rep_80.startswith("Heads up\n\n"),
        "replica keeps the fenced command byte-exact": any(
            line.rstrip() == LONG_COMMAND for line in rep_lines
        ),
        "replica keeps the fenced delimiters": "```bash" in rep_plain
        and rep_plain.rstrip("\n").splitlines()[-1] == "```",
        "replica keeps a blank line before the fence": "\n\n```bash" in rep_80,
        "replica keeps a blank line after the fence": "```\n\n" in rep_80,
        "replica keeps the bold style on a terminal": bold_rep != ""
        and bold_rep == bold_prod,
        "replica keeps the inline-code style on a terminal": code_rep != ""
        and code_rep == code_prod,
        "replica keeps dim fenced delimiters": "\x1b[2m```bash" in rep_ansi,
    }

    print("=== CHECKS ===")
    for label, ok in checks.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    print()

    if all(checks.values()):
        print(
            "=> Replica proven: unbounded prose layout plus trimmed line "
            "re-emission is width-invariant, keeps every character, and "
            "preserves production's terminal styling. The terminal owns the "
            "fold and can reflow it on resize."
        )
        sys.exit(0)
    print("=> Replica proof failed; inspect the dumps above before editing production.")
    sys.exit(1)


if __name__ == "__main__":
    main()
