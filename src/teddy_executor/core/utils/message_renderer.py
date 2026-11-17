"""Render a communicating turn's Message body for a terminal."""

from rich.console import Console
from rich.text import Text
from rich.theme import Theme


def inline_code_theme() -> Theme:
    """Return the theme used for inline code in rendered prose.

    The Core deliverable derives rich's default ``markdown.code`` style minus
    its background; the skeleton returns the default theme so the Wiring tracer
    can wire the console without implementing the rendering rules.
    """
    return Theme()


def render_message_body(body: str, console: Console) -> None:
    """Emit a Message body to ``console``.

    The Core deliverable replaces this with per-segment prose and fence
    rendering; the skeleton emits the whole body as a ``Text`` renderable so
    rich markup never parses the body, proving the boundary connects.
    """
    console.print(Text(body))
