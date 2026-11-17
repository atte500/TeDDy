"""Spike: strip the inline-code background and verify the whole Markdown surface.

Two review questions drove this spike:

1. Inline code such as `teddy resume -p` currently renders on a filled background.
   Can the fill be removed while keeping the token styling? The spike derives the
   override from rich's own default ``markdown.code`` style, clearing only the
   background colour, and renders the same paragraph with and without it.
2. Which Markdown constructs actually render, and which fall through as plain
   text? The spike renders one comprehensive sample covering headings h1-h6,
   emphasis, strikethrough, inline code, links, images, autolinks, escapes,
   block quotes (including nested), unordered/ordered/nested/task lists, GFM
   tables, horizontal rules, fenced code, indented code, reference links, and
   inline HTML, then runs a marker-stripping probe per construct.

Run it in your own terminal for real colour and your real width:

    uv run python spikes/prototypes/message-rendering/show_markdown_spec.py

Flags:

    --width N    pretend the terminal is N columns wide
    --name NAME  agent name in the framing header (default: TeDDy)

Colour previews (open in a browser):

    .tmp/message-rendering/inline-default.svg
    .tmp/message-rendering/inline-adjusted.svg
    .tmp/message-rendering/spec-adjusted.svg
"""

from __future__ import annotations

import argparse
import io
import re
from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console
from rich.default_styles import DEFAULT_STYLES
from rich.markdown import Markdown
from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text
from rich.theme import Theme

try:
    from teddy_executor.core.utils.markdown import _FENCE_RE as FENCE_RE

    GRAMMAR = "production _FENCE_RE"
except Exception as exc:  # pragma: no cover - fallback for a bare checkout
    FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
    GRAMMAR = f"local copy ({type(exc).__name__}: {exc})"

OUT_DIR = Path(".tmp/message-rendering")

INLINE_SAMPLE = (
    "Inline code today: run `teddy resume -p` to resume, and `array[i]` stays intact.\n"
    "A second span: `--pipeline` and `stage_on_message: false`.\n"
)

FULL_SAMPLE = r"""# Heading level 1

## Heading level 2

### Heading level 3

#### Heading level 4

##### Heading level 5

###### Heading level 6

A paragraph with **bold**, *italic*, ***bold italic***, ~~struck through~~, and inline `code_span()` plus a [link](https://example.com) and an ![image alt text](https://example.com/x.png).

Autolink: <https://example.com> and escaped \*asterisks\* stay literal.

> A block quote line.
>
> > A nested block quote.

- bullet one
- bullet two
  - nested bullet
    - deeper bullet

1. ordered one
2. ordered two
   1. nested ordered A
   2. nested ordered B

- [ ] open task
- [x] done task

| Column A | Column B | Column C |
| :------- | :------: | -------: |
| left     | center   | right    |
| 1        | 2        | 3        |

---

```python
def greet(name: str) -> str:
    return f"hello {name}"
```

    an indented code block line

A reference link uses [the spec][spec] syntax.

[spec]: https://example.com/spec

Inline HTML like <b>bold</b> and <br> is not interpreted by rich, so it stays visible as text.
"""


@dataclass(frozen=True)
class Segment:
    kind: str
    info: str
    content: str
    opening: str = ""
    closing: str = ""


@dataclass(frozen=True)
class Probe:
    label: str
    source: str
    content: str | None
    forbidden: str | None


def split(body: str) -> list[Segment]:
    """Split a body into prose and fence segments, keeping raw delimiter lines."""
    lines = body.split("\n")
    segments: list[Segment] = []
    prose: list[str] = []
    index = 0
    while index < len(lines):
        match = FENCE_RE.match(lines[index])
        if match is None:
            prose.append(lines[index])
            index += 1
            continue
        if prose and any(line.strip() for line in prose):
            segments.append(Segment("prose", "", "\n".join(prose)))
        prose = []
        fence = match.group(1)
        info = match.group(2).strip()
        code: list[str] = []
        closing = ""
        cursor = index + 1
        while cursor < len(lines):
            candidate = FENCE_RE.match(lines[cursor])
            if (
                candidate is not None
                and candidate.group(1)[0] == fence[0]
                and len(candidate.group(1)) >= len(fence)
                and not candidate.group(2).strip()
            ):
                closing = lines[cursor]
                break
            code.append(lines[cursor])
            cursor += 1
        segments.append(Segment("fence", info, "\n".join(code), lines[index], closing))
        index = cursor + 1
    if prose and any(line.strip() for line in prose):
        segments.append(Segment("prose", "", "\n".join(prose)))
    return segments


def code_style_without_background() -> tuple[Style, Style]:
    """Return (current, stripped) for rich's `markdown.code` theme entry.

    The stripped style keeps every attribute except the background colour, so
    inline code stays coloured and weighted but sits on the terminal default.
    """
    current = DEFAULT_STYLES.get("markdown.code") or Style()
    stripped = Style(
        color=current.color,
        bold=current.bold,
        dim=current.dim,
        italic=current.italic,
        underline=current.underline,
        strike=current.strike,
    )
    return current, stripped


def adjusted_theme() -> Theme:
    _, stripped = code_style_without_background()
    return Theme({"markdown.code": stripped})


def render_live(theme: Theme | None, width: int, body: str) -> None:
    """Render with OPTION E, widening each fence console to its longest line."""
    for segment in split(body):
        if segment.kind == "prose":
            Console(width=width, theme=theme, markup=False, highlight=False).print(
                Markdown(segment.content)
            )
            continue
        longest = max((len(line) for line in segment.content.split("\n")), default=0)
        block = Console(
            width=max(width, longest), theme=theme, markup=False, highlight=False
        )
        typer.echo()
        block.print(Text(segment.opening, style="dim"))
        block.print(
            Syntax(
                segment.content,
                segment.info or "text",
                word_wrap=False,
                padding=(0, 0),
                background_color="default",
            )
        )
        if segment.closing:
            block.print(Text(segment.closing, style="dim"))
        typer.echo()


def markdown_svg(
    path: Path, theme: Theme | None, width: int, text: str, title: str
) -> None:
    console = Console(
        width=width,
        theme=theme,
        record=True,
        force_terminal=True,
        markup=False,
        highlight=False,
    )
    console.print(Markdown(text))
    console.save_svg(str(path), title=title)


def spec_svg(path: Path, theme: Theme | None, width: int, body: str, title: str) -> None:
    console = Console(
        width=width,
        theme=theme,
        record=True,
        force_terminal=True,
        markup=False,
        highlight=False,
    )
    for segment in split(body):
        if segment.kind == "prose":
            console.print(Markdown(segment.content))
            continue
        console.print(Text(segment.opening, style="dim"))
        console.print(
            Syntax(
                segment.content,
                segment.info or "text",
                word_wrap=False,
                padding=(0, 0),
                background_color="default",
            )
        )
        if segment.closing:
            console.print(Text(segment.closing, style="dim"))
    console.save_svg(str(path), title=title)


PROBES: list[Probe] = [
    Probe("heading h1", "# Title", "Title", "# Title"),
    Probe("heading h2", "## Sub", "Sub", "## Sub"),
    Probe("heading h3", "### Third", "Third", "###"),
    Probe("bold", "**strong** text", "strong", "**"),
    Probe("italic", "an *em* word", "em", "*em*"),
    Probe("bold-italic", "***both***", "both", "***"),
    Probe("strikethrough", "~~gone~~", "gone", "~~"),
    Probe("inline code", "a `code()` span", "code()", "`"),
    Probe("link", "[label](https://example.com)", "label", "](https://"),
    Probe("image", "![alt text](https://example.com/x.png)", "alt text", "!["),
    Probe("autolink", "<https://example.com>", "https://example.com", "<https"),
    Probe("escape", r"\*literal asterisks\*", "*literal asterisks*", None),
    Probe("block quote", "> quoted line", "quoted line", "> quoted"),
    Probe("nested quote", "> > inner line", "inner line", "> >"),
    Probe("unordered list", "- first\n- second", "first", None),
    Probe("ordered list", "1. one\n2. two", "one", "1. one"),
    Probe("task list", "- [ ] open\n- [x] done", "open", "[ ]"),
    Probe("table", "| a | b |\n| :-- | --: |\n| 1 | 2 |", "a", "| a |"),
    Probe("horizontal rule", "above\n\n---\n\nbelow", "below", "---"),
    Probe("fenced code", "```python\nprint(1)\n```", "print(1)", "```"),
    Probe("indented code", "    indented_line()", "indented_line()", "    indented_line"),
    Probe("reference link", "[spec][s]\n\n[s]: https://example.com", "spec", "[spec][s]"),
]


def run_probe(probe: Probe, theme: Theme | None, width: int) -> str:
    buffer = io.StringIO()
    console = Console(
        file=buffer,
        width=width,
        force_terminal=False,
        theme=theme,
        markup=False,
        highlight=False,
    )
    console.print(Markdown(probe.source))
    out = buffer.getvalue()
    content_ok = probe.content is None or probe.content in out
    forbidden_ok = probe.forbidden is None or probe.forbidden not in out
    if content_ok and forbidden_ok:
        return "rendered"
    if not content_ok:
        return f"content missing ({probe.content!r})"
    return f"raw marker left ({probe.forbidden!r})"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--name", default="TeDDy")
    args = parser.parse_args()

    live = Console()
    width = args.width or live.width
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    default_style, stripped_style = code_style_without_background()
    theme = adjusted_theme()

    typer.secho(f"fence grammar: {GRAMMAR}", fg=typer.colors.BRIGHT_BLACK)
    typer.secho(f"terminal width: {width} columns", fg=typer.colors.BRIGHT_BLACK)
    typer.secho(
        f"default  markdown.code: color={default_style.color} bold={default_style.bold} bgcolor={default_style.bgcolor}",
        fg=typer.colors.BRIGHT_BLACK,
    )
    typer.secho(
        f"adjusted markdown.code: color={stripped_style.color} bold={stripped_style.bold} bgcolor={stripped_style.bgcolor}",
        fg=typer.colors.BRIGHT_BLACK,
    )

    typer.secho(
        "\n=== INLINE CODE — default theme (filled background, as today) ===",
        fg=typer.colors.MAGENTA,
        bold=True,
    )
    Console(width=width).print(Markdown(INLINE_SAMPLE))

    typer.secho(
        "\n=== INLINE CODE — adjusted theme (background removed) ===",
        fg=typer.colors.MAGENTA,
        bold=True,
    )
    Console(width=width, theme=theme).print(Markdown(INLINE_SAMPLE))

    typer.secho(
        "\n=== FULL MARKDOWN SPEC — adjusted theme ===",
        fg=typer.colors.MAGENTA,
        bold=True,
    )
    typer.echo()
    typer.secho(f"--- MESSAGE from {args.name} ---", fg=typer.colors.CYAN)
    render_live(theme, width, FULL_SAMPLE)

    typer.secho(
        "\n=== FEATURE MATRIX — heuristic marker check ===",
        fg=typer.colors.MAGENTA,
        bold=True,
    )
    for probe in PROBES:
        typer.echo(f"  {probe.label:20s} {run_probe(probe, theme, width)}")

    markdown_svg(
        OUT_DIR / "inline-default.svg", None, width, INLINE_SAMPLE, "Inline code — default"
    )
    markdown_svg(
        OUT_DIR / "inline-adjusted.svg",
        theme,
        width,
        INLINE_SAMPLE,
        "Inline code — adjusted",
    )
    spec_svg(
        OUT_DIR / "spec-adjusted.svg",
        theme,
        width,
        FULL_SAMPLE,
        "Markdown spec — adjusted",
    )

    typer.secho(
        f"\nartifacts: {OUT_DIR}/inline-default.svg, {OUT_DIR}/inline-adjusted.svg, "
        f"{OUT_DIR}/spec-adjusted.svg",
        fg=typer.colors.BRIGHT_BLACK,
    )
    typer.secho(
        "Note: a piped capture strips colour, so the background difference is only "
        "visible in your terminal or in the SVG previews.",
        fg=typer.colors.BRIGHT_BLACK,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
