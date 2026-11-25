"""Probe: which emission strategy keeps the line breaks of a prose block?

MRE 05 showed the replica emitting every logical line of a prose block
concatenated onto ONE output line ("Heads upThis is..."): the heading check
and the blank-line check failed while all content checks passed. The layout
(``render_lines`` at an unbounded width) is proven correct; the suspect is the
emission call. ``console.print(Segments(line), soft_wrap=True)`` appears to
treat a bare segment list as an already-complete renderable and swallow the
line break that a ``Text`` renderable receives.

This probe renders the same prose block with four emission strategies and dumps
the exact bytes, so the newline mechanism is observed rather than guessed:

A. per-line ``Segments`` (current replica)
B. per-line ``Segments`` with an explicit ``end="\\n"``
C. per-line ``Text`` rebuilt from each line's segments
D. one ``Segments`` stream with explicit ``\\n`` separators
"""

from __future__ import annotations

import io
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from rich.console import Console
from rich.markdown import Markdown
from rich.segment import Segment, Segments
from rich.text import Text

from teddy_executor.core.utils.message_renderer import inline_code_theme

BIG = 10_000

PARAGRAPH = (
    "This is a deliberately long paragraph that exceeds a narrow terminal "
    "width, so a reflowable renderer must leave it as one logical line for "
    "the terminal to fold."
)

BODY = f"""## Heads up

{PARAGRAPH}

- **Bold** should lose its asterisks.
- Inline `teddy resume -p` should lose backticks.
"""


def _trim(line: list[Segment]) -> list[Segment]:
    """Drop layout padding from one rendered line, keeping styles."""
    trimmed = list(line)
    while trimmed:
        last = trimmed[-1]
        text = last.text.rstrip()
        if text:
            trimmed[-1] = Segment(text, last.style)
            return trimmed
        trimmed.pop()
    return trimmed


def _write(strategy: str, content: str, console: Console) -> None:
    options = console.options.update(max_width=BIG)
    lines = console.render_lines(Markdown(content), options=options, pad=False)

    if strategy == "A_segments_perline":
        for line in lines:
            console.print(Segments(_trim(line)), soft_wrap=True)
    elif strategy == "B_segments_perline_end":
        for line in lines:
            console.print(Segments(_trim(line)), soft_wrap=True, end="\n")
    elif strategy == "C_text_perline":
        for line in lines:
            text = Text()
            for segment in line:
                if segment.control:
                    continue
                text.append(segment.text, style=segment.style)
            trimmed = text.rstrip()
            console.print(trimmed if trimmed is not None else text, soft_wrap=True)
    elif strategy == "D_segments_joined":
        stream: list[Segment] = []
        for index, line in enumerate(lines):
            if index:
                stream.append(Segment("\n"))
            stream.extend(_trim(line))
        console.print(Segments(stream), soft_wrap=True)
    else:
        raise ValueError(strategy)


def main() -> None:
    strategies = (
        "A_segments_perline",
        "B_segments_perline_end",
        "C_text_perline",
        "D_segments_joined",
    )
    for strategy in strategies:
        buffer = io.StringIO()
        console = Console(
            file=buffer,
            width=80,
            force_terminal=False,
            color_system=None,
            theme=inline_code_theme(),
        )
        _write(strategy, BODY, console)
        out = buffer.getvalue()
        lines = out.split("\n")
        heading_alone = any(line == "Heads up" for line in lines)
        blank_after_heading = out.startswith("Heads up\n\n")
        print(f"=== {strategy} ===")
        print(f"  heading on its own line:      {heading_alone}")
        print(f"  one blank line after heading: {blank_after_heading}")
        print(f"  emitted line count:           {len(lines)}")
        for index, line in enumerate(lines):
            print(f"    [{index:02d}] {len(line):4d} | {line[:90]!r}")
        print()


if __name__ == "__main__":
    main()
