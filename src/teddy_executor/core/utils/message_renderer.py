"""Render a communicating turn's Message body for a terminal."""

from rich.console import Console
from rich.default_styles import DEFAULT_STYLES
from rich.markdown import Markdown
from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text
from rich.theme import Theme

from teddy_executor.core.utils.markdown import MessageSegment, split_fenced_segments


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

    Prose renders through ``Markdown`` so its syntax markers disappear. Fenced
    blocks keep their own delimiter lines, are dimmed at the boundary, and keep
    their bytes so a copied command runs unchanged. An empty body prints one
    blank line, matching the newline the raw ``typer.secho`` path emits.
    """
    segments = split_fenced_segments(body)
    if not segments:
        console.print(Text(""))
        return

    for segment in segments:
        if segment.kind == "prose":
            console.print(Markdown(segment.content))
        else:
            _emit_fenced_block(segment, console)


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
