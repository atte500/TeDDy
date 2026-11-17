"""Probe: what actually happens to bracketed tokens in a Message body.

The slice `00-20-message-body-rendering.md` claims:

    If prose contains `[TODO]`, `[!]`, or `[✓]`, then the tokens render
    literally, because `Console.print(str)` would treat them as markup tags
    and drop them.

That claim needs measuring. This probe renders a matrix of bracket forms
through every path the renderer could use:

    secho                      `typer.secho(text)` — today's production path
    print(str)                 `console.print(text)` — markup parsing on a bare string
    print(str, markup=False)   same, with markup parsing disabled
    print(Text)                `console.print(Text(text))` — literal, no parsing
    print(Markdown)            `console.print(Markdown(text))` — the proposed prose path

For each pair it records whether the token survived verbatim, was consumed as
markup, or raised. It also prints rich's own tag regex, so the rule is quoted
from the library instead of remembered.

Run from the project root:

    uv run python spikes/prototypes/message-rendering/probe_bracket_tokens.py
"""

from __future__ import annotations

import io
from collections.abc import Callable
from contextlib import redirect_stdout

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text

WIDTH = 100

TOKENS: list[tuple[str, str]] = [
    ("upper-word", "[TODO] fix the edge case"),
    ("bang", "[!] blocking constraint"),
    ("check", "[✓] completed task"),
    ("question", "[?] open question"),
    ("debt", "[DEBT] refactor opportunity"),
    ("hold", "[HOLD] paused"),
    ("lower-word", "[note] lowercase unknown tag"),
    ("valid-style", "[bold]bold[/bold]"),
    ("colour", "[red]red[/red]"),
    ("link-tag", "[link]reference[/link]"),
    ("hex", "[#ff0000]hex[/#ff0000]"),
    ("plain-brackets", "plain [brackets] mid-sentence"),
    ("index", "array[0] and list[i]"),
    ("ref-def", "[TODO]: https://example.com"),
    ("md-link", "see [docs](https://example.com)"),
]


def _console(buf: io.StringIO, *, markup: bool = True) -> Console:
    return Console(file=buf, width=WIDTH, force_terminal=False, markup=markup)


def render_secho(text: str) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        typer.secho(text)
    return buf.getvalue()


def render_console_str(text: str) -> str:
    buf = io.StringIO()
    _console(buf).print(text)
    return buf.getvalue()


def render_console_str_no_markup(text: str) -> str:
    buf = io.StringIO()
    _console(buf, markup=False).print(text)
    return buf.getvalue()


def render_text(text: str) -> str:
    buf = io.StringIO()
    _console(buf).print(Text(text))
    return buf.getvalue()


def render_markdown(text: str) -> str:
    buf = io.StringIO()
    _console(buf).print(Markdown(text))
    return buf.getvalue()


PATHS: dict[str, Callable[[str], str]] = {
    "secho": render_secho,
    "print(str)": render_console_str,
    "print(str,markup=False)": render_console_str_no_markup,
    "print(Text)": render_text,
    "print(Markdown)": render_markdown,
}


def tag_pattern() -> str:
    try:
        from rich.markup import RE_TAGS

        return RE_TAGS.pattern
    except Exception as exc:
        return f"unavailable ({type(exc).__name__}: {exc})"


def probe(label: str, text: str) -> str | None:
    """Render one token through every path; return the first raising path."""
    print(f"\n[{label}] raw={text!r}")
    first_failure: str | None = None
    for name, render in PATHS.items():
        try:
            out = render(text).rstrip("\n")
        except Exception as exc:
            first_failure = first_failure or name
            print(f"  {name:24s} RAISED  {type(exc).__name__}: {exc}")
            continue
        intact = text in out
        print(f"  {name:24s} ok      intact={str(intact):5s} out={out!r}")
    return first_failure


def prose_block() -> None:
    """A realistic prose block with several bracket forms at once."""
    body = (
        "Status mix: [TODO] wire the renderer, [✓] split the segments, "
        "[!] keep fences byte-exact.\n\n"
        "An inline tag like [note] and a real Markdown link "
        "[the spec](https://example.com) sit in the same paragraph.\n"
    )
    print("\n--- combined prose block ---")
    for name in ("print(str)", "print(Markdown)"):
        try:
            out = PATHS[name](body).rstrip("\n")
            print(f"\n{name}:")
            for line in out.splitlines():
                print(f"  {line}")
        except Exception as exc:
            print(f"\n{name}: RAISED {type(exc).__name__}: {exc}")


def main() -> int:
    print(f"rich tag regex: {tag_pattern()}")
    print(f"paths probed: {', '.join(PATHS)}")

    raising: dict[str, str] = {}
    for label, text in TOKENS:
        failed = probe(label, text)
        if failed:
            raising[label] = failed

    prose_block()

    print("\n--- summary ---")
    if raising:
        for label, path in raising.items():
            print(f"raises on {path:24s} -> {label}")
    else:
        print("no path raised on any probed token")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
