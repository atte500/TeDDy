"""MRE: does a Message body reflow on terminal resize?

A terminal reflows a line only when it SOFT-wrapped it (the terminal broke the
line at its edge). If the program HARD-wraps (it inserts "\\n" mid-paragraph),
the break is permanent and a later resize cannot undo it.

This probe renders one long paragraph at two console widths through:

1. the current ``render_message_body`` (Rich ``Markdown`` + ``console.print``),
2. a candidate soft-wrap variant (``soft_wrap=True``),
3. a candidate wide-console variant (wrap width far beyond any real line).

If (1) is width-dependent but (2) or (3) is width-invariant, the current
renderer hard-wraps and the candidate hands wrapping back to the terminal.
"""

from __future__ import annotations

import io
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "src"))

from rich.console import Console
from rich.markdown import Markdown

from teddy_executor.core.utils.message_renderer import render_message_body

PARAGRAPH = (
    "This is a deliberately long paragraph that a communicating turn would "
    "print as its **Message** body. It keeps going so that it clearly exceeds "
    "a narrow terminal width, forcing the renderer to choose between "
    "hard-wrapping the text itself and leaving one long logical line for the "
    "terminal to soft-wrap and reflow when the user resizes the window."
)


def _console(buf: io.StringIO, width: int) -> Console:
    return Console(file=buf, width=width, force_terminal=False, color_system=None)


def _render_current(width: int) -> str:
    buf = io.StringIO()
    render_message_body(PARAGRAPH, _console(buf, width))
    return buf.getvalue()


def _render_soft_wrap(width: int) -> str:
    buf = io.StringIO()
    _console(buf, width).print(Markdown(PARAGRAPH), soft_wrap=True)
    return buf.getvalue()


def _render_wide(_width: int) -> str:
    # Wrap width pinned huge so Rich cannot wrap; independent of the terminal.
    buf = io.StringIO()
    Console(file=buf, width=10_000, force_terminal=False, color_system=None).print(
        Markdown(PARAGRAPH)
    )
    return buf.getvalue()


def _describe(label: str, text: str) -> None:
    lines = text.rstrip("\n").split("\n")
    print(f"--- {label} ---")
    for i, line in enumerate(lines):
        print(f"  [{i:02d}] len={len(line):3d} | {line}")
    print()


def main() -> None:
    current_80, current_40 = _render_current(80), _render_current(40)
    soft_80, soft_40 = _render_soft_wrap(80), _render_soft_wrap(40)
    wide_80, wide_40 = _render_wide(80), _render_wide(40)

    _describe("CURRENT render_message_body @ width=80", current_80)
    _describe("CURRENT render_message_body @ width=40", current_40)
    _describe("CANDIDATE soft_wrap @ width=80", soft_80)
    _describe("CANDIDATE soft_wrap @ width=40", soft_40)
    _describe("CANDIDATE wide-console @ width=80", wide_80)
    _describe("CANDIDATE wide-console @ width=40", wide_40)

    current_depends = current_80 != current_40
    soft_depends = soft_80 != soft_40
    wide_depends = wide_80 != wide_40

    print("=== VERDICT ===")
    print(f"current renderer output depends on console width:     {current_depends}")
    print(f"soft_wrap variant output depends on console width:    {soft_depends}")
    print(f"wide-console variant output depends on console width: {wide_depends}")
    print()
    if current_depends and not soft_depends:
        print(
            "=> Root cause confirmed: current renderer hard-wraps at print "
            "width; soft_wrap=True is width-invariant, so the terminal owns "
            "wrapping and can reflow on resize."
        )
    elif current_depends and not wide_depends:
        print(
            "=> Root cause confirmed: current renderer hard-wraps; a wide "
            "render console is width-invariant and lets the terminal reflow."
        )
    elif not current_depends:
        print("=> Renderer is already width-invariant; the bug is elsewhere.")
    else:
        print(
            "=> Inconclusive: both candidates still depend on width; inspect "
            "the printed line lengths above for the mechanism."
        )


if __name__ == "__main__":
    main()
