"""Spike: live terminal preview of the proposed `## Message` rendering.

Run it in your own terminal to see real colours at your real width:

    uv run python spikes/prototypes/message-rendering/render_live.py

Each mode prints the same body so the trade-off is visible instead of
described:

    raw     today's output: blank separator, cyan header, Markdown body verbatim
    rich    fences as bare text: prose through `rich.markdown.Markdown`, each
            fenced block printed verbatim with no visual boundary
    fenced  fences in a syntax block: same layout, but each fenced block goes
            through `rich.syntax.Syntax` with `word_wrap=False`, so it keeps its
            bytes AND carries a themed background marking where it starts and
            ends
    syntax-clean
            syntax colours with the theme background removed and blank lines
            around the block, so the code reads as a block instead of a painted
            stripe
    syntax-fenced
            same as `syntax-clean`, plus dim ``` delimiters and an optional
            language tag around the block, so the boundary is textual AND the
            tokens stay coloured
    literal fence lines kept and dimmed: same layout, but each fence prints its
            literal ``` delimiters in a dim style, so the boundary is visible as
            text instead of colour and survives redirection
    fold    the rejected variant: one whole-body `Markdown` render, which folds
            the over-long handoff command at the terminal width and breaks
            copy-paste

Flags:

    --only raw|rich|fenced|literal|syntax-clean|syntax-fenced|fold|all
                               print one mode (default: all)
    --sample message|code      which body to render (default: message). `code`
                               packs long snippets in bash, python, typescript,
                               json, yaml, sql, dockerfile, an unknown info
                               string, and one fence with no tag at all, so the
                               lexer behaviour is visible on real content
    --width N                  pretend the terminal is N columns wide
    --name NAME                agent name in the header (default: TeDDy)

Nothing is written to disk. Redirecting the output disables colour, which is
how the real implementation would behave behind a TTY gate.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Callable

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.text import Text

# Mirrors `_FENCE_RE` in teddy_executor/core/utils/markdown.py: up to three
# leading spaces, a run of 3+ backticks or tildes, then an optional info string.
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")

HANDOFF = (
    "teddy start -a developer -m 'Render the Message body with rich.markdown "
    "behind a TTY check and keep redirects raw' -c "
    "'docs/project/specs/interactive-session-workflow.md'"
)

BODY = f"""\
**Formatted Message rendering — yes, cheap.** The body already goes through the
console framing, so only the body's formatting changes.

What changes on screen:

- Headings lose their `##` markers.
- Bullets render with a glyph and a hanging indent.
- Inline code sits on a subtle background.
- Fenced blocks keep their exact bytes, so handoffs stay copy-pasteable.

Handoff example:

```bash
{HANDOFF}
```

| Option       | Scope             | Cost               |
| :----------- | :---------------- | :----------------- |
| Rendering    | one adapter       | none               |
| Auto-staging | new outbound port | mutates your index |

TL;DR: rendering is a contained adapter change; staging needs a git port.
"""

CODE_BODY = """\
The same ideas, quoted across the stack. Every block carries at least one line
far wider than a terminal, so folding, cropping, and injected padding all show
up plainly.

```bash
set -euo pipefail
uv run python -m teddy_executor.cli resume --session 20261117-message-rendering-preview --agent developer --pipeline --max-cost 4.50
git log --oneline --decorate --graph --since='2026-11-01' --grep='message-rendering' origin/main..HEAD
```

```python
def render_message(body: str, console: Console, *, stage: str | None = None) -> str:
    if stage == "raw":
        return console.export_text(styles=False)
    return _segmented_render(body, console, stage=stage, fence_padding=(0, 0), word_wrap=False)
```

```typescript
export type Segment = { kind: "prose" | "fence"; info: string; content: string; longestLine: number };
export const splitSegments = (body: string, options: SplitOptions = DEFAULT_SPLIT_OPTIONS): Segment[] => body.split("\\n").reduce(collectSegments, []);
```

```json
{"agent": "pathfinder", "model": "anthropic/claude-sonnet-4.5", "require_approval": false, "turn_context": ["docs/project/specs/interactive-session-workflow.md"], "max_turns": null}
```

```yaml
staging:
  stage_on_message: false        # opt-in: default off, so a hand-curated index is never absorbed silently
  skip_when_index_dirty: true    # one-line notice instead of absorbing a hunk you staged yourself
```

```sql
select s.id, s.slug, count(t.id) as turns, max(t.created_at) as last_turn_at from sessions s left join turns t on t.session_id = s.id group by s.id, s.slug order by last_turn_at desc;
```

```dockerfile
RUN uv sync --frozen --no-dev && uv run python -m teddy_executor.cli context --only --no-copy > /tmp/context.md && head -40 /tmp/context.md
```

```teddy-plan
# An info string rich cannot resolve: `Syntax` must fall back to plain text and leave these bytes untouched, because a plan fragment is not source code.
```

```
A fence with no info string at all: the renderer falls back to `text`, keeps this deliberately over-long line intact, and still marks where the block starts and ends.
```
"""

SAMPLES: dict[str, str] = {"message": BODY, "code": CODE_BODY}


def split_segments(body: str) -> list[tuple[str, str, str]]:
    """Split a Markdown body into ('prose', '', text) and ('fence', info, code)."""
    lines = body.split("\n")
    segments: list[tuple[str, str, str]] = []
    prose: list[str] = []
    index = 0
    while index < len(lines):
        match = FENCE_RE.match(lines[index])
        if match is None:
            prose.append(lines[index])
            index += 1
            continue
        if prose:
            segments.append(("prose", "", "\n".join(prose)))
            prose = []
        fence = match.group(1)
        info = match.group(2).strip()
        code: list[str] = []
        cursor = index + 1
        while cursor < len(lines):
            closing = FENCE_RE.match(lines[cursor])
            if (
                closing is not None
                and closing.group(1)[0] == fence[0]
                and len(closing.group(1)) >= len(fence)
                and not closing.group(2).strip()
            ):
                break
            code.append(lines[cursor])
            cursor += 1
        segments.append(("fence", info, "\n".join(code)))
        index = cursor + 1
    if prose:
        segments.append(("prose", "", "\n".join(prose)))
    return segments


def emit_header(name: str) -> None:
    """Reproduce the framing `SessionOrchestrator` prints before a body."""
    typer.echo()
    typer.secho(f"--- MESSAGE from {name} ---", fg=typer.colors.CYAN)


def show_raw(width: int, name: str, body: str) -> None:
    emit_header(name)
    typer.echo(body, nl=False)
    typer.echo()


def show_rich(width: int, name: str, body: str) -> None:
    emit_header(name)
    for kind, _info, content in split_segments(body):
        if kind == "prose":
            Console(width=width).print(Markdown(content))
            continue
        longest = max((len(line) for line in content.split("\n")), default=0)
        Console(width=max(width, longest)).print(Text(content))
    typer.echo()


def show_fenced(width: int, name: str, body: str) -> None:
    """Render fences through `Syntax` so each block keeps a visible boundary.

    `padding=(0, 0)` is required: rich defaults to `(0, 1)`, which prepends a
    space to every fenced line and would corrupt a copy-pasted `FIND:` block.
    """
    emit_header(name)
    for kind, info, content in split_segments(body):
        if kind == "prose":
            Console(width=width).print(Markdown(content))
            continue
        longest = max((len(line) for line in content.split("\n")), default=0)
        Console(width=max(width, longest)).print(
            Syntax(content, info or "text", word_wrap=False, padding=(0, 0))
        )
    typer.echo()


def show_fence_lines(width: int, name: str, body: str) -> None:
    """Render fences with their literal delimiters, dimmed.

    The command bytes stay on one line because the fence console is sized to the
    block's longest line. The delimiters are re-emitted so the boundary survives
    redirection and screenshots, and so copying the whole block yields the same
    bytes the raw output yields today.
    """
    emit_header(name)
    for kind, info, content in split_segments(body):
        if kind == "prose":
            Console(width=width).print(Markdown(content))
            continue
        longest = max((len(line) for line in content.split("\n")), default=0)
        fence_console = Console(width=max(width, longest))
        fence_console.print(Text(f"```{info}", style="dim"))
        fence_console.print(Text(content))
        fence_console.print(Text("```", style="dim"))
    typer.echo()


def show_syntax_clean(width: int, name: str, body: str) -> None:
    """Syntax highlighting with the theme background removed and blank spacing.

    `background_color="default"` paints each token on the terminal's own
    background, so the fill colour that made OPTION B look painted is gone.
    Blank lines before and after the block separate the code from the
    surrounding prose, which is what the "no good spacing" complaint was about.
    """
    emit_header(name)
    for kind, info, content in split_segments(body):
        if kind == "prose":
            Console(width=width).print(Markdown(content))
            continue
        longest = max((len(line) for line in content.split("\n")), default=0)
        console = Console(width=max(width, longest))
        typer.echo()
        console.print(
            Syntax(
                content,
                info or "text",
                word_wrap=False,
                padding=(0, 0),
                background_color="default",
            )
        )
        typer.echo()
    typer.echo()


def show_syntax_fenced(width: int, name: str, body: str) -> None:
    """Syntax highlighting with no background, dim fences, and blank spacing.

    Combines the token colours the user liked with the textual boundary of
    OPTION C, so the block is visibly delimited, still copy-pasteable end to
    end, and no longer painted with the theme's background colour.
    """
    emit_header(name)
    for kind, info, content in split_segments(body):
        if kind == "prose":
            Console(width=width).print(Markdown(content))
            continue
        longest = max((len(line) for line in content.split("\n")), default=0)
        console = Console(width=max(width, longest))
        typer.echo()
        console.print(Text(f"```{info}" if info else "```", style="dim"))
        console.print(
            Syntax(
                content,
                info or "text",
                word_wrap=False,
                padding=(0, 0),
                background_color="default",
            )
        )
        console.print(Text("```", style="dim"))
        typer.echo()
    typer.echo()


def show_fold(width: int, name: str, body: str) -> None:
    emit_header(name)
    Console(width=width).print(Markdown(body))
    typer.echo()


MODES: dict[str, tuple[str, Callable[[int, str, str], None]]] = {
    "raw": ("CURRENT — raw Markdown, exactly what you see today", show_raw),
    "rich": ("OPTION A — fences as bare text, no visual boundary", show_rich),
    "fenced": ("OPTION B — syntax block, themed background (weird fill)", show_fenced),
    "syntax-clean": ("OPTION D — syntax colours, no background, blank spacing", show_syntax_clean),
    "syntax-fenced": ("OPTION E — syntax colours, no background, dim fences", show_syntax_fenced),
    "literal": ("OPTION C — fence lines kept and dimmed, boundary is text", show_fence_lines),
    "fold": ("REJECTED — one whole-body render, handoff folded mid-argument", show_fold),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=[*MODES, "all"], default="all")
    parser.add_argument("--sample", choices=sorted(SAMPLES), default="message")
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--name", default="TeDDy")
    args = parser.parse_args()

    width = args.width or Console().width
    body = SAMPLES[args.sample]
    selected = list(MODES.items()) if args.only == "all" else [(args.only, MODES[args.only])]

    typer.secho(
        f"\nterminal width: {width} columns | sample: {args.sample}",
        fg=typer.colors.BRIGHT_BLACK,
    )
    for _key, (label, render) in selected:
        typer.secho(f"\n=== {label} ===", fg=typer.colors.MAGENTA, bold=True)
        render(width, args.name, body)

    typer.secho(
        "\nNote: the real implementation gates on the output being a TTY and "
        "falls back to the raw bytes above when it is not.",
        fg=typer.colors.BRIGHT_BLACK,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
