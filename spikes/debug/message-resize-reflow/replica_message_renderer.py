"""Sandbox replica of ``message_renderer`` with terminal-owned prose wrapping.

Difference against production: prose is laid out at an unbounded width and
re-emitted line by line with its styles intact, so Rich inserts no fold of its
own and the terminal owns wrapping. A later resize can then reflow the text,
while production lays each block out at ``console.width`` and writes hard
newlines that no resize can undo. Fenced blocks are copied verbatim from
production.
"""

from rich.console import Console
from rich.markdown import Markdown
from rich.segment import Segment, Segments
from rich.syntax import Syntax
from rich.text import Text

from teddy_executor.core.utils.markdown import MessageSegment, split_fenced_segments

# Wrap width pinned far beyond any terminal line, so Rich cannot fold or crop
# prose internally: the terminal performs the only fold, and it can reflow it.
PROSE_RENDER_WIDTH = 10_000


def render_message_body(body: str, console: Console) -> None:
    """Emit a Message body with prose left for the terminal to wrap."""
    segments = split_fenced_segments(body)
    if not segments:
        console.print(Text(""))
        return

    for segment in segments:
        if segment.kind == "prose":
            _emit_prose(segment.content, console)
        else:
            _emit_fenced_block(segment, console)


def _emit_prose(content: str, console: Console) -> None:
    """Emit one prose block as logical lines the terminal can reflow.

    ``render_lines`` returns pre-rendered, styled segments per logical line.
    They are re-emitted as ONE segment stream with explicit newlines: printing
    each line as its own ``Segments`` renderable makes Rich swallow the line
    break and concat the block onto a single line. One stream keeps every break,
    and ``soft_wrap`` stops Rich from re-folding or cropping, so the terminal
    owns the fold.
    """
    options = console.options.update(max_width=PROSE_RENDER_WIDTH)
    lines = console.render_lines(Markdown(content), options=options, pad=False)
    # A trailing blank line would double up with the fence block's own lead-in.
    while lines and not _trim_trailing_blanks(lines[-1]):
        lines.pop()
    stream: list[Segment] = []
    for index, line in enumerate(lines):
        if index:
            stream.append(Segment("\n"))
        stream.extend(_trim_trailing_blanks(line))
    # A bare ``Segments`` renderable emits no trailing newline, so the break
    # that separates this block from the next one must be part of the stream.
    stream.append(Segment("\n"))
    console.print(Segments(stream), soft_wrap=True)


def _trim_trailing_blanks(line: list[Segment]) -> list[Segment]:
    """Drop layout padding so a resize cannot reflow invisible trailing spaces."""
    trimmed = list(line)
    while trimmed:
        last = trimmed[-1]
        text = last.text.rstrip()
        if text:
            trimmed[-1] = Segment(text, last.style)
            return trimmed
        trimmed.pop()
    return trimmed


def _emit_fenced_block(segment: MessageSegment, console: Console) -> None:
    """Emit one fenced block between blank lines, with dim verbatim delimiters.

    ``soft_wrap=True`` keeps an over-long line whole: rich wraps or crops at the
    console width otherwise, and a folded command cannot be copied.
    """
    console.print()
    console.print(Text(segment.opening, style="dim"))
    console.print(
        Syntax(
            segment.content,
            segment.info or "text",
            word_wrap=False,
            padding=(0, 0),
            background_color="default",
        ),
        soft_wrap=True,
    )
    if segment.closing:
        console.print(Text(segment.closing, style="dim"))
    console.print()
