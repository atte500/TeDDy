"""Probe: what the theme override changes, measured at the ANSI level.

An earlier attempt searched for a standalone ``\\x1b[40m`` and reported "no
background" on every path, including the default theme where the fill is plainly
there. Rich composes one SGR run per style, so a fill arrives as a parameter
inside ``\\x1b[1;36;40m`` and never standalone. This probe parses SGR parameters,
self-tests the parser, and then settles the questions the slice still leaves
open:

    inline code     does stripping ``markdown.code``'s background remove the
                    fill while keeping colour and weight?
    code blocks     which fills survive, and which mechanism owns them?
    indented code   can the fill be removed through ``Markdown(code_theme=...)``?
    images          is text lost, or only the image hoisted out of position?
    heading/lists   what do h1, task lists, and horizontal rules actually emit?

Run from the project root:

    uv run python spikes/prototypes/message-rendering/probe_theme_and_edges.py

No files are written and no styling is emitted, so the output survives piping.
"""

from __future__ import annotations

import io
import re

from rich.console import Console
from rich.default_styles import DEFAULT_STYLES
from rich.markdown import Markdown
from rich.style import Style
from rich.syntax import Syntax
from rich.theme import Theme

WIDTH = 72
SGR_RE = re.compile(r"\x1b\[([0-9;]*)m")
OSC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")

INLINE = "run `teddy resume -p` and `array[i]` now\n"
INLINE_FRAGMENTS = ("teddy resume -p", "array[i]")
FENCED = "```python\nprint(1)\n```\n"
INDENTED = "prose line\n\n    print(1)\n"
IMG_INLINE = "before ![alt text](https://example.com/x.png) after\n"
IMG_ALT = "before alt text after\n"
H1 = "# Title\n"
TASKS = "- [ ] open\n- [x] done\n"
RULE = "above\n\n---\n\nbelow\n"
THEME_CANDIDATES = ("monokai", "ansi_dark", "bw", "default", "friendly")


def sgr_backgrounds(text: str) -> list[str]:
    """Return SGR parameter runs that set a background fill.

    ``49`` is the default-background reset and is not a fill. ``48`` introduces
    an extended background whose payload must be skipped, or its colour numbers
    (e.g. ``48;2;39;40;34``) are misread as their own parameters.
    """
    found: list[str] = []
    for params in SGR_RE.findall(text):
        numbers = [int(part) for part in params.split(";") if part.isdigit()]
        index = 0
        while index < len(numbers):
            number = numbers[index]
            if number in (38, 48):
                mode = numbers[index + 1] if index + 1 < len(numbers) else None
                span = 5 if mode == 2 else 3 if mode == 5 else 1
                if number == 48:
                    found.append(params)
                    break
                index += span + 1
                continue
            if 40 <= number <= 47 or 100 <= number <= 107:
                found.append(params)
                break
            index += 1
    return found


def plain(text: str) -> str:
    return OSC_RE.sub("", SGR_RE.sub("", text))


def strip_background(style: Style) -> Style:
    """Keep every attribute of ``style`` except the background fill."""
    return Style(
        color=style.color,
        bold=style.bold,
        dim=style.dim,
        italic=style.italic,
        underline=style.underline,
        strike=style.strike,
    )


INLINE_THEME = Theme({"markdown.code": strip_background(DEFAULT_STYLES["markdown.code"])})


def _console(**kwargs: object) -> Console:
    return Console(
        file=io.StringIO(),
        width=WIDTH,
        force_terminal=True,
        color_system="truecolor",
        markup=False,
        highlight=False,
        **kwargs,
    )


def render_markdown(
    markup: str, theme: Theme | None = None, code_theme: str = "monokai"
) -> str:
    console = _console(theme=theme)
    console.print(Markdown(markup, code_theme=code_theme))
    return console.file.getvalue()


def render_own_fence(code: str, lexer: str = "python") -> str:
    console = _console()
    console.print(
        Syntax(code, lexer, word_wrap=False, padding=(0, 0), background_color="default")
    )
    return console.file.getvalue()


def main() -> int:
    print("--- detector self-test ---")
    for label, sample in (
        ("font only", "\x1b[1;36mX\x1b[0m"),
        ("standard fill", "\x1b[1;36;40mX\x1b[0m"),
        ("default background", "\x1b[1;36;49mX\x1b[0m"),
        ("truecolour fill", "\x1b[48;2;39;40;34mX\x1b[0m"),
        ("truecolour font only", "\x1b[38;2;102;217;239;49mX\x1b[0m"),
    ):
        print(f"  {label:24s} fills={sgr_backgrounds(sample)}")

    default_style = DEFAULT_STYLES["markdown.code"]
    stripped_style = strip_background(default_style)
    print("\n--- inline code ---")
    print(
        f"  default style   color={default_style.color} bold={default_style.bold} "
        f"bgcolor={default_style.bgcolor}"
    )
    print(
        f"  stripped style  color={stripped_style.color} bold={stripped_style.bold} "
        f"bgcolor={stripped_style.bgcolor}"
    )
    for label, theme in (("default theme", None), ("stripped theme", INLINE_THEME)):
        out = render_markdown(INLINE, theme=theme)
        kept = all(fragment in plain(out) for fragment in INLINE_FRAGMENTS)
        print(f"  {label:14s} fills={sgr_backgrounds(out)} text_kept={kept}")

    print("\n--- code block fills ---")
    print(
        "  ours: Syntax(background_color='default')  "
        f"fills={sgr_backgrounds(render_own_fence('print(1)'))}"
    )
    print(
        "  Markdown fenced, monokai                 "
        f"fills={sgr_backgrounds(render_markdown(FENCED, theme=INLINE_THEME))}"
    )
    print(
        "  Markdown indented, monokai               "
        f"fills={sgr_backgrounds(render_markdown(INDENTED, theme=INLINE_THEME))}"
    )

    print("\n--- code_theme candidates on an indented block ---")
    for name in THEME_CANDIDATES:
        try:
            background = str(Syntax.get_theme(name).background_color)
        except Exception as exc:  # noqa: BLE001 - unknown theme names are data here
            background = f"unavailable ({type(exc).__name__})"
        fills = sgr_backgrounds(
            render_markdown(INDENTED, theme=INLINE_THEME, code_theme=name)
        )
        print(f"  {name:10s} theme_bg={background:22s} fill={'yes' if fills else 'no'}")

    print("\n--- images ---")
    for label, markup in (("raw image syntax", IMG_INLINE), ("alt text substitution", IMG_ALT)):
        rendered = plain(render_markdown(markup)).rstrip("\n")
        print(f"  {label}:")
        for line in rendered.split("\n"):
            print(f"    |{line}")

    print("\n--- heading, task list, horizontal rule ---")
    for label, markup in (("h1", H1), ("task list", TASKS), ("horizontal rule", RULE)):
        rendered = plain(render_markdown(markup)).rstrip("\n")
        print(f"  {label}:")
        for line in rendered.split("\n"):
            print(f"    |{line}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
