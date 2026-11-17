"""Probe: what `style="dim"` actually emits on degraded terminals.

The slice leaves one Key Unknown open: whether `style="dim"` reads as a boundary
on a 16-colour or `NO_COLOR` terminal. Perception cannot be measured by code,
but the emitted bytes can. This probe captures the exact output of a dim
delimiter line under every colour system rich supports and under the
environment toggles that disable colour, then reports whether the dim attribute
(SGR 2) survives and what the plain-text fallback looks like.

Run from the project root:

    uv run python spikes/prototypes/message-rendering/probe_dim_legibility.py

No files are written and no styling is emitted, so the output survives piping.
"""

from __future__ import annotations

import io
import os
import re

from rich.console import Console
from rich.text import Text

WIDTH = 40
SGR_RE = re.compile(r"\x1b\[([0-9;]*)m")


def _console(**kwargs: object) -> Console:
    return Console(
        file=io.StringIO(),
        width=WIDTH,
        force_terminal=True,
        markup=False,
        highlight=False,
        **kwargs,
    )


def render_delimiters(console: Console) -> str:
    """Emit the same dim opening/content/closing shape the renderer will use."""
    console.print(Text("```bash", style="dim"))
    console.print(Text("echo hi"))
    console.print(Text("```", style="dim"))
    return console.file.getvalue()


def sgr_runs(text: str) -> list[list[int]]:
    return [
        [int(part) for part in params.split(";") if part.isdigit()]
        for params in SGR_RE.findall(text)
    ]


def has_dim(runs: list[list[int]]) -> bool:
    return any(2 in params for params in runs)


def plain(text: str) -> str:
    return SGR_RE.sub("", text)


def report(label: str, console: Console) -> None:
    text = render_delimiters(console)
    runs = sgr_runs(text)
    print(
        f"{label:22s} dim={has_dim(runs)} color_system={console.color_system} "
        f"no_color={console.no_color}"
    )
    print(f"{'':22s} runs={runs} plain={plain(text)!r}")


def main() -> int:
    print("--- explicit colour systems (force_terminal=True) ---")
    for label, system in (
        ("truecolor", "truecolor"),
        ("256", "256"),
        ("standard (16)", "standard"),
        ("none", None),
    ):
        report(label, _console(color_system=system))

    print("\n--- rich no_color toggle (force_terminal=True) ---")
    report("no_color=True", _console(no_color=True))
    report("no_color=False", _console(no_color=False))

    print("\n--- environment toggles (default Console, force_terminal=True) ---")
    saved = {key: os.environ.get(key) for key in ("NO_COLOR", "TERM", "FORCE_COLOR")}
    try:
        os.environ.pop("FORCE_COLOR", None)
        os.environ["NO_COLOR"] = "1"
        os.environ.pop("TERM", None)
        report("NO_COLOR=1", _console())

        os.environ.pop("NO_COLOR", None)
        os.environ["TERM"] = "dumb"
        report("TERM=dumb", _console())

        os.environ.pop("TERM", None)
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
