"""Unit tests for rendering a Message body to a console."""

import io
import re

from rich.console import Console
from rich.default_styles import DEFAULT_STYLES

from teddy_executor.core.utils.message_renderer import (
    inline_code_theme,
    render_message_body,
)

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _render(body: str, *, width: int = 80, terminal: bool = False) -> str:
    buffer = io.StringIO()
    console = Console(
        file=buffer,
        width=width,
        force_terminal=terminal,
        markup=False,
        highlight=False,
    )
    render_message_body(body, console)
    return buffer.getvalue()


def _plain(text: str) -> str:
    return _ANSI_RE.sub("", text)


def test_prose_renders_without_markdown_markers():
    out = _plain(_render("Some **bold** prose.\n"))

    assert "bold" in out
    assert "**" not in out


def test_empty_body_renders_a_single_newline():
    assert _render("") == "\n"


def test_fence_is_separated_from_surrounding_prose_by_blank_lines():
    out = _plain(_render("Before.\n```bash\necho hi\n```\nAfter.\n"))

    assert "\n\n```bash" in out
    assert "```\n\n" in out


def test_over_long_fenced_line_stays_unbroken():
    long_line = "x" * 100

    out = _plain(_render(f"```text\n{long_line}\n```\n", width=40))

    assert long_line in out


def test_tilde_fence_keeps_its_own_delimiters():
    out = _plain(_render("~~~yaml\nkey: value\n~~~\n"))

    assert "~~~yaml" in out
    assert "```" not in out


def test_unclosed_fence_emits_no_closing_delimiter():
    out = _plain(_render("```python\nprint(1)\n"))

    assert "```python" in out
    assert out.count("```") == 1


def test_fence_delimiters_are_dim_on_a_terminal():
    out = _render("```bash\necho hi\n```\n", terminal=True)

    assert "\x1b[2m```bash" in out
    assert "echo hi" in _plain(out)
    assert "\x1b[2m```" in out


def test_inline_code_theme_drops_background_but_keeps_colour_and_weight():
    style = inline_code_theme().styles.get("markdown.code")
    default = DEFAULT_STYLES["markdown.code"]

    assert style is not None
    assert style.bgcolor is None
    assert style.color == default.color
    assert style.bold == default.bold


def test_inline_code_theme_inherits_other_markdown_styles():
    assert inline_code_theme().styles.get("markdown.strong") is not None
