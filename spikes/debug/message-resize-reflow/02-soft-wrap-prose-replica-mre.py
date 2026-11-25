"""Proof: soft-wrapped prose lets the terminal reflow a Message body.

Production ``render_message_body`` prints prose through Rich ``Markdown``
without ``soft_wrap``, so Rich folds each block at ``console.width`` and writes
hard newlines. A terminal can only reflow lines it soft-wrapped itself, which
is why resizing leaves the Message wrapped at its print width.

This probe renders a realistic Message body (heading, paragraph, bullet list,
fenced command with an over-long line) through production and through the
sandbox replica ``replica_message_renderer.py`` at console widths 80 and 40.

Pass criteria:
1. Production output differs between widths (the defect).
2. Replica output is byte-identical between widths (terminal owns the fold).
3. Replica still strips prose markers, keeps the heading text, and preserves
   the fenced command byte-exact on one line.
"""

from __future__ import annotations

import io
import pathlib
import sys
from typing import Callable

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "spikes/debug/message-resize-reflow"))

from rich.console import Console

import replica_message_renderer
from teddy_executor.core.utils.message_renderer import render_message_body

PARAGRAPH = (
    "This is a deliberately long paragraph that a communicating turn would "
    "print as its Message body. It keeps going so that it clearly exceeds a "
    "narrow terminal width, forcing the renderer to choose between wrapping "
    "the text itself and leaving one logical line for the terminal to fold "
    "and reflow when the user resizes the window."
)

LONG_COMMAND = (
    "uv run teddy context -c README.md -c pyproject.toml "
    "-c docs/project/PROJECT.md --only"
)

BODY = f"""## Heads up

{PARAGRAPH}

- **Bold** should lose its asterisks.
- Inline `teddy resume -p` should lose backticks.

```bash
echo before
{LONG_COMMAND}
echo after
```
"""


def _render(renderer: Callable[[str, Console], None], width: int) -> str:
    buf = io.StringIO()
    console = Console(file=buf, width=width, force_terminal=False, color_system=None)
    renderer(BODY, console)
    return buf.getvalue()


def _show(label: str, text: str) -> None:
    print(f"--- {label} ---")
    for i, line in enumerate(text.rstrip("\n").split("\n")):
        print(f"  [{i:02d}] len={len(line):4d} | {line}")
    print()


def main() -> None:
    prod_80 = _render(render_message_body, 80)
    prod_40 = _render(render_message_body, 40)
    rep_80 = _render(replica_message_renderer.render_message_body, 80)
    rep_40 = _render(replica_message_renderer.render_message_body, 40)

    _show("PRODUCTION @ width=80", prod_80)
    _show("PRODUCTION @ width=40", prod_40)
    _show("REPLICA soft_wrap @ width=80", rep_80)
    _show("REPLICA soft_wrap @ width=40", rep_40)

    replica_lines = rep_80.splitlines()
    checks = {
        "production output depends on width (defect)": prod_80 != prod_40,
        "replica output is width-invariant (fix)": rep_80 == rep_40,
        "production splits the paragraph at 80": PARAGRAPH not in prod_80,
        "production splits the paragraph at 40": PARAGRAPH not in prod_40,
        "replica keeps paragraph on one line at 80": PARAGRAPH in rep_80,
        "replica keeps paragraph on one line at 40": PARAGRAPH in rep_40,
        "replica strips bold markers": "**Bold**" not in rep_80
        and "Bold should lose its asterisks." in rep_80,
        "replica strips inline-code backticks": "`teddy resume -p`" not in rep_80
        and "teddy resume -p should lose backticks." in rep_80,
        "replica renders heading text without hashes": "## Heads up" not in rep_80
        and any(line.strip() == "Heads up" for line in replica_lines),
        "replica preserves the long fenced command byte-exact": any(
            line.rstrip() == LONG_COMMAND for line in replica_lines
        ),
        "replica keeps fence delimiters": "```bash" in rep_80
        and rep_80.rstrip("\n").splitlines()[-1].strip() == "```",
        "production also preserves the long fenced command": any(
            line.rstrip() == LONG_COMMAND for line in prod_80.splitlines()
        ),
    }

    print("=== CHECKS ===")
    for label, ok in checks.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    print()

    if all(checks.values()):
        print(
            "=> Replica proven: soft_wrap prose is width-invariant, so the "
            "terminal owns wrapping and can reflow on resize; formatting and "
            "fenced bytes survive intact."
        )
        sys.exit(0)

    print("=> Replica proof failed; inspect the dumps above before editing production.")
    sys.exit(1)


if __name__ == "__main__":
    main()
