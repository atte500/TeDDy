"""Spike: render a realistic Message body with one code block nested inside another.

The segmentation design splits a Message body on fence delimiters so prose can be
formatted while every fenced block keeps its exact bytes. Nesting is where that
design can fail: a four-backtick fence wrapping a three-backtick block must stay
one segment, or the inner block shatters the outer wrapper and the trailing prose
falls into a fence that never closes.

This spike renders two realistic bodies with the accepted treatment (syntax
colours, no theme background, dimmed verbatim delimiters, blank lines around each
block) and compares two splitters on the same input:

    length-aware   a closing fence needs the same character and a run at least as
                   long as the opener (the production rule)
    naive          the first fence-like line closes the block

Run it in your own terminal for real colour at your real width:

    uv run python spikes/prototypes/message-rendering/show_nested_blocks.py

Flags:

    --sample nested-backticks|tilde-wrapper|all   which body to render (default: all)
    --width N                                    pretend the terminal is N wide
    --name NAME                                  agent name in the header

Nothing is written to disk.
"""

from __future__ import annotations

import argparse
import io
import re
from dataclasses import dataclass

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.text import Text

try:
    from teddy_executor.core.utils.markdown import _FENCE_RE as FENCE_RE
    from teddy_executor.core.utils.markdown import strip_trailing_open_fence

    GRAMMAR = "production _FENCE_RE"
except Exception as exc:  # pragma: no cover - fallback for a bare checkout
    FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
    strip_trailing_open_fence = None
    GRAMMAR = f"local copy ({type(exc).__name__}: {exc})"


@dataclass(frozen=True)
class Segment:
    kind: str
    info: str
    content: str
    opening: str = ""
    closing: str = ""


def split(body: str, *, length_aware: bool = True) -> list[Segment]:
    """Split a body into prose and fence segments, keeping raw delimiter lines.

    With ``length_aware`` the closing fence must reuse the opener's character and
    be at least as long, which is the rule that keeps a nested block intact.
    Without it, the first fence-like line ends the block.
    """
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
            if candidate is not None:
                same_char = candidate.group(1)[0] == fence[0]
                long_enough = (
                    len(candidate.group(1)) >= len(fence) if length_aware else True
                )
                if same_char and long_enough and not candidate.group(2).strip():
                    closing = lines[cursor]
                    break
            code.append(lines[cursor])
            cursor += 1
        segments.append(Segment("fence", info, "\n".join(code), lines[index], closing))
        index = cursor + 1
    if prose and any(line.strip() for line in prose):
        segments.append(Segment("prose", "", "\n".join(prose)))
    return segments


def _child_console(parent: Console, longest_line: int) -> Console:
    """A console sharing the parent's stream, widened to the block's longest line."""
    return Console(
        file=parent.file,
        width=max(parent.width, longest_line),
        force_terminal=parent.is_terminal,
        color_system=parent.color_system,
        markup=False,
        highlight=False,
    )


def render(console: Console, body: str, *, length_aware: bool = True) -> None:
    """Render with OPTION E: prose through Markdown, fences verbatim and coloured."""
    for segment in split(body, length_aware=length_aware):
        if segment.kind == "prose":
            console.print(Markdown(segment.content))
            continue
        longest = max((len(line) for line in segment.content.split("\n")), default=0)
        block = _child_console(console, longest)
        console.file.write("\n")
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
        console.file.write("\n")


def capture(body: str, width: int, *, length_aware: bool = True) -> str:
    buffer = io.StringIO()
    console = Console(
        file=buffer,
        width=width,
        force_terminal=False,
        markup=False,
        highlight=False,
    )
    render(console, body, length_aware=length_aware)
    return buffer.getvalue()


def delimiters(segments: list[Segment]) -> list[str]:
    return [segment.opening.lstrip()[:1] or "?" for segment in segments]


def fences(body: str, *, length_aware: bool = True) -> list[Segment]:
    return [segment for segment in split(body, length_aware=length_aware) if segment.kind == "fence"]


def summary(body: str, width: int) -> list[str]:
    strict = fences(body)
    naive = fences(body, length_aware=False)
    rendered = capture(body, width)
    rendered_fences = fences(rendered)
    rendered_lines = {line.rstrip() for line in rendered.split("\n")}
    missing = sorted(
        {
            line
            for segment in strict
            for line in segment.content.split("\n")
            if line.strip() and line.rstrip() not in rendered_lines
        }
    )
    return [
        f"fences, length-aware splitter : {len(strict)}  {delimiters(strict)}",
        f"fences, naive splitter        : {len(naive)}  {delimiters(naive)}",
        f"fences, rendered output       : {len(rendered_fences)}  {delimiters(rendered_fences)}",
        f"fenced content lines missing  : {len(missing)}",
        *[f"    missing: {line!r}" for line in missing],
    ]


SAMPLES: dict[str, str] = {
    "nested-backticks": (
        "The slice document format, with a command inside the example. The outer fence\n"
        "uses four backticks so the inner block survives copy-paste into\n"
        "`docs/project/slices/`:\n"
        "\n"
        "````markdown\n"
        "# Slice: Stage on Message Reply\n"
        "- **Status:** Planned\n"
        "\n"
        "## Verification\n"
        "\n"
        "1. **Adapter contract:**\n"
        "   Run the adapter tests before wiring the hook:\n"
        "\n"
        "```bash\n"
        "uv run python -m pytest tests/suites/unit/test_git_index_adapter.py "
        "tests/suites/unit/test_session_lifecycle_manager.py -q --maxfail=1\n"
        "```\n"
        "\n"
        "2. **Flag default:**\n"
        "   Confirm `staging.stage_on_message` still defaults to `false`.\n"
        "````\n"
        "\n"
        "Copying that block into a slice keeps the inner fence intact, which is the\n"
        "whole point of the longer outer run.\n"
    ),
    "tilde-wrapper": (
        "A tilde wrapper buys the same nesting with a different character, so no length\n"
        "juggling is needed at all:\n"
        "\n"
        "~~~markdown\n"
        "# Slice: Stage on Message Reply\n"
        "\n"
        "```python\n"
        "def stage_all(executor: IShellExecutor) -> ShellOutput:\n"
        '    return executor.execute("git add -A")\n'
        "```\n"
        "~~~\n"
        "\n"
        "The inner block keeps its own delimiter even though the outer one is a tilde.\n"
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", choices=[*SAMPLES, "all"], default="all")
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--name", default="TeDDy")
    args = parser.parse_args()

    live = Console(markup=False, highlight=False)
    width = args.width or live.width
    selected = list(SAMPLES.items()) if args.sample == "all" else [(args.sample, SAMPLES[args.sample])]

    typer.secho(f"fence grammar: {GRAMMAR}", fg=typer.colors.BRIGHT_BLACK)
    typer.secho(f"terminal width: {width} columns", fg=typer.colors.BRIGHT_BLACK)

    for title, body in selected:
        typer.secho(f"\n=== sample: {title} ===", fg=typer.colors.MAGENTA, bold=True)
        typer.secho("\n--- source ---", fg=typer.colors.BRIGHT_BLACK)
        typer.echo(body, nl=False)

        typer.secho("\n--- rendered ---", fg=typer.colors.BRIGHT_BLACK)
        live.file.write("\n")
        live.print(Text(f"--- MESSAGE from {args.name} ---", style="cyan"))
        render(live, body)

        typer.secho("--- verdict ---", fg=typer.colors.BRIGHT_BLACK)
        for line in summary(body, width):
            typer.echo(f"  {line}")

    if strip_trailing_open_fence is not None:
        nested = SAMPLES["nested-backticks"]
        unchanged = strip_trailing_open_fence(nested) == nested
        typer.secho(
            f"\nstrip_trailing_open_fence on the nested body: "
            f"{'unchanged' if unchanged else 'MODIFIED'}",
            fg=typer.colors.BRIGHT_BLACK,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
