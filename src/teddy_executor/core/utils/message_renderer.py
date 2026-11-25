"""Render a communicating turn's Message body for a terminal."""

from rich.console import Console
from rich.default_styles import DEFAULT_STYLES
from rich.markdown import Markdown
from rich.segment import Segment, Segments
from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text
from rich.theme import Theme

from teddy_executor.core.utils.markdown import MessageSegment, split_fenced_segments

# Wrap width pinned far beyond any terminal line, so Rich cannot fold or crop
# prose internally; the terminal performs the only fold and can reflow it.
PROSE_RENDER_WIDTH = 10_000


def inline_code_theme() -> Theme:
    """Return a theme whose inline code drops the fill but keeps its styling.

    Rich's default ``markdown.code`` style paints a background behind inline
    code. This derives that style with every attribute except ``bgcolor``, so a
    code span stays coloured and bold on the terminal's own background. The
    ``Theme`` keeps ``inherit=True`` so every other Markdown style survives.
    """
    default = DEFAULT_STYLES["markdown.code"]
    stripped = Style(
        color=default.color,
        bold=default.bold,
        dim=default.dim,
        italic=default.italic,
        underline=default.underline,
        strike=default.strike,
    )
    return Theme({"markdown.code": stripped})


def render_message_body(body: str, console: Console) -> None:
    """Emit a Message body to ``console`` as prose and copy-pasteable fences.

    Prose renders through ``Markdown`` so its syntax markers disappear, and is
    laid out at an unbounded width so the terminal owns the fold: resizing the
    terminal reflows the text instead of leaving it hard-wrapped at its print
    width. Fenced blocks keep their own delimiter lines, are dimmed at the
    boundary, and keep their bytes so a copied command runs unchanged. An empty
    body prints one blank line, matching the newline the raw ``typer.secho``
    path emits.
    """
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
    break and concatenate the block onto one line. One stream keeps every break,
    and ``soft_wrap`` stops Rich from re-folding or cropping, so the terminal
    owns the fold.
    """
    options = console.options.update(max_width=PROSE_RENDER_WIDTH)
    lines = console.render_lines(Markdown(content), options=options, pad=False)
    # A trailing blank line would double up with a following fence's lead-in.
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
