"""Dump real emitted bytes for prose emission strategies.

Turn 6 showed production lines ending at exactly the console width even when the
visible text is short, so Rich Markdown pads each line to the full width with
trailing spaces. Trailing padding is invisible at print time but it is hard
content: resizing narrower re-wraps every padded line into a ragged mess.

Turn 7 showed that neither ``soft_wrap=True`` alone nor ``console.print(...,
width=BIG)`` yields width-invariant output, and that rendering via
``render_lines(options.update(max_width=BIG))`` somehow emitted <=85-char lines.

This probe dumps the actual bytes for each strategy at widths 80 and 40 and
counts trailing-padded lines, so the mechanism is observable rather than
inferred.
"""

from __future__ import annotations

import importlib.metadata
import io
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text

from teddy_executor.core.utils import message_renderer as prod
from teddy_executor.core.utils.markdown import split_fenced_segments
from teddy_executor.core.utils.message_renderer import inline_code_theme

BIG = 10_000

PARAGRAPH = (
    "This is a deliberately long paragraph that a communicating turn would "
    "print as its Message body. It keeps going so that it clearly exceeds a "
    "narrow terminal width, forcing the renderer to choose between wrapping "
    "the text itself and leaving one logical line for the terminal to fold "
    "and reflow when the user resizes the window."
)

BULLET_TEXT = "Inline teddy resume -p should lose backticks."

LONG_COMMAND = (
    "uv run teddy context -c README.md -c pyproject.toml "
    "-c docs/project/PROJECT.md --only"
)

BODY = f"""## Heads up

{PARAGRAPH}

- **Bold** should lose its asterisks.
- {BULLET_TEXT}

```bash
echo before
{LONG_COMMAND}
echo after
```
"""

STRATEGIES = (
    "current",
    "soft_wrap_only",
    "wide_print",
    "render_lines_text",
    "scratch_strip",
)


def _scratch_render(content: str, console: Console) -> str:
    """Render Markdown at an unbounded width on a scratch console."""
    capture = Console(
        file=io.StringIO(),
        width=BIG,
        force_terminal=console.is_terminal,
        color_system=console.color_system,
        theme=inline_code_theme(),
    )
    capture.print(Markdown(content), soft_wrap=True)
    return capture.file.getvalue()  # type: ignore[union-attr]


def _emit_text(line: str, console: Console) -> None:
    stripped = line.rstrip()
    if console.color_system:
        console.print(Text.from_ansi(stripped), soft_wrap=True)
    else:
        console.print(Text(stripped), soft_wrap=True)


def _render_lines_text(content: str, console: Console) -> None:
    options = console.options.update(max_width=BIG)
    lines = console.render_lines(Markdown(content), options=options, pad=False)
    for line in lines:
        text = Text()
        for segment in line:
            if segment.control:
                continue
            text.append(segment.text, style=segment.style)
        console.print(text.rstrip(), soft_wrap=True)


def _scratch_strip(content: str, console: Console) -> None:
    for line in _scratch_render(content, console).rstrip("\n").split("\n"):
        _emit_text(line, console)


def _prose(strategy: str, content: str, console: Console) -> None:
    if strategy == "current":
        console.print(Markdown(content))
    elif strategy == "soft_wrap_only":
        console.print(Markdown(content), soft_wrap=True)
    elif strategy == "wide_print":
        console.print(Markdown(content), width=BIG, soft_wrap=True)
    elif strategy == "render_lines_text":
        _render_lines_text(content, console)
    elif strategy == "scratch_strip":
        _scratch_strip(content, console)
    else:
        raise ValueError(strategy)


def _render(strategy: str, width: int) -> str:
    buf = io.StringIO()
    console = Console(
        file=buf,
        width=width,
        force_terminal=False,
        color_system=None,
        theme=inline_code_theme(),
    )
    for segment in split_fenced_segments(BODY):
        if segment.kind == "prose":
            _prose(strategy, segment.content, console)
        else:
            prod._emit_fenced_block(segment, console)
    return buf.getvalue()


def _padded_lines(text: str) -> int:
    return sum(1 for line in text.split("\n") if line != line.rstrip())


def _dump(text: str) -> None:
    for i, line in enumerate(text.rstrip("\n").split("\n")):
        marker = "PAD" if line != line.rstrip() else "   "
        print(f"    [{i:02d}] {len(line):5d} {marker} | {line[:96]!r}")


def main() -> None:
    print("rich version:", importlib.metadata.version("rich"))
    print()

    for strategy in STRATEGIES:
        out80 = _render(strategy, 80)
        out40 = _render(strategy, 40)
        print(f"=== {strategy} ===")
        print(f"  width-invariant:          {out80 == out40}")
        print(f"  paragraph contiguous @80: {PARAGRAPH in out80}")
        print(f"  paragraph contiguous @40: {PARAGRAPH in out40}")
        print(f"  bullet contiguous @80:    {BULLET_TEXT in out80}")
        print(f"  bullet contiguous @40:    {BULLET_TEXT in out40}")
        print(f"  heading text, no hashes:  {'## Heads up' not in out80}")
        print(f"  fenced command byte-exact: {any(l.rstrip() == LONG_COMMAND for l in out80.splitlines())}")
        print(f"  padded lines @80:         {_padded_lines(out80)}")
        print(f"  padded lines @40:         {_padded_lines(out40)}")
        print("  @40 emitted lines:")
        _dump(out40)
        if out80 != out40:
            print("  @80 emitted lines:")
            _dump(out80)
        print()


if __name__ == "__main__":
    main()
