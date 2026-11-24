"""Look-alike preview of the waiting indicator shown while a plan is generated.

Run in a real terminal:

    uv run python spikes/prototypes/waiting-indicator/preview.py

Today the waiting line is printed once and the telemetry block prints below it
before the model call starts:

    [001] add-retry-backoff | Waiting for pathfinder to respond...
    • Model: llama3.1:70b
    • Context: 12.4k / 131.1k tokens
    • Session Cost: $0.0042

An animated glyph can only rewrite the last line on screen, so a trailing
glyph forces one of two trade-offs:

    tail           The waiting line becomes the animated line: the glyph trails
                   the text and telemetry prints above it as it arrives.
                   Telemetry is visible immediately; the waiting line ends up
                   at the bottom of the block.
    tail-deferred  The waiting line stays where it is and animates alone;
                   telemetry is buffered and printed once the wait ends. The
                   final layout is identical to today, but the model/cost
                   block arrives after the wait instead of before it.

`below` keeps the waiting line static and animates a bare glyph on its own
transient line underneath the telemetry. The glyph carries no label, because the
waiting line above already names the agent, and it erases on completion so the
settled layout is byte-identical to today.

Flags:
    --option {tail,tail-deferred,below,all}
    --seconds SECONDS   Simulated wait per design (default 4).
    --glyph {dots,quadrant}
    --elapsed           Append elapsed seconds to the glyph.
    --retry             Simulate an empty-response retry notice.
"""

from __future__ import annotations

import argparse
import time

from rich.console import Console
from rich.live import Live
from rich.text import Text

GLYPHS = {
    "dots": "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏",
    "quadrant": "◰◳◲◱",
}
FRAME_SECONDS = 0.1

TURN = "001"
SESSION = "add-retry-backoff"
AGENT = "pathfinder"

BANNER = f"[{TURN}] {SESSION} | Waiting for {AGENT} to respond..."

TELEMETRY = (
    "• Model: llama3.1:70b",
    "• Context: 12.4k / 131.1k tokens",
    "• Session Cost: $0.0042",
)

RETRY_NOTICE = "Empty response received (Attempt 1/3). Retrying..."


def _spinner(started: float, glyph: str, show_elapsed: bool) -> str:
    """Return the current glyph frame, optionally followed by elapsed seconds."""
    frames = GLYPHS[glyph]
    frame = frames[int((time.monotonic() - started) / FRAME_SECONDS) % len(frames)]
    if not show_elapsed:
        return frame
    return f"{frame} {int(time.monotonic() - started)}s"


def _tail_line(started: float, glyph: str, show_elapsed: bool) -> Text:
    """The waiting line with the animated glyph appended after its text."""
    return Text.from_markup(
        f"[cyan]{BANNER} {_spinner(started, glyph, show_elapsed)}[/cyan]"
    )


def preview_tail(
    console: Console, seconds: float, glyph: str, show_elapsed: bool, show_retry: bool
) -> None:
    """Trailing glyph on the waiting line; telemetry prints above it."""
    started = time.monotonic()

    def render() -> Text:
        return _tail_line(started, glyph, show_elapsed)

    with Live(render(), console=console, refresh_per_second=10, transient=True) as live:
        time.sleep(min(0.6, seconds * 0.2))
        for line in TELEMETRY:
            console.print(f"[blue]{line}[/blue]")
            time.sleep(0.05)
        if show_retry:
            console.print(f"[yellow]{RETRY_NOTICE}[/yellow]")
        while time.monotonic() - started < seconds:
            live.update(render())
            time.sleep(FRAME_SECONDS)

    console.print(f"[cyan]{BANNER}[/cyan]")
    console.print("[dim]→ plan.md written[/dim]")


def preview_tail_deferred(
    console: Console, seconds: float, glyph: str, show_elapsed: bool, show_retry: bool
) -> None:
    """Trailing glyph on the waiting line; telemetry prints after the wait."""
    started = time.monotonic()
    buffered: list[str] = []

    def render() -> Text:
        return _tail_line(started, glyph, show_elapsed)

    with Live(render(), console=console, refresh_per_second=10, transient=True) as live:
        time.sleep(min(0.6, seconds * 0.2))
        buffered.extend(f"[blue]{line}[/blue]" for line in TELEMETRY)
        if show_retry:
            buffered.append(f"[yellow]{RETRY_NOTICE}[/yellow]")
        while time.monotonic() - started < seconds:
            live.update(render())
            time.sleep(FRAME_SECONDS)

    console.print(f"[cyan]{BANNER}[/cyan]")
    for line in buffered:
        console.print(line)
    console.print("[dim]→ plan.md written[/dim]")


def preview_below(
    console: Console, seconds: float, glyph: str, show_elapsed: bool, show_retry: bool
) -> None:
    """Static waiting line, then a bare animated glyph below the telemetry.

    The glyph is unlabelled because the waiting line above already names the
    agent, and any suffix would reintroduce the text this variant strips.
    """
    console.print(f"\n[cyan]{BANNER}[/cyan]")
    time.sleep(min(0.6, seconds * 0.2))
    for line in TELEMETRY:
        console.print(f"[blue]{line}[/blue]")
        time.sleep(0.05)
    console.print("")

    started = time.monotonic()

    def render() -> Text:
        return Text(_spinner(started, glyph, show_elapsed=False), style="cyan")

    with Live(render(), console=console, refresh_per_second=10, transient=True) as live:
        if show_retry:
            console.print(f"[yellow]{RETRY_NOTICE}[/yellow]")
        while time.monotonic() - started < seconds:
            live.update(render())
            time.sleep(FRAME_SECONDS)

    console.print("[dim]→ plan.md written[/dim]")


def _print_static_settled_layout(console: Console) -> None:
    """For a non-TTY run: show the three settled layouts without animating."""
    console.print("\n[bold]tail (settled)[/bold]")
    for line in TELEMETRY:
        console.print(f"[blue]{line}[/blue]")
    console.print(f"[cyan]{BANNER}[/cyan]")
    console.print("[dim]→ plan.md written[/dim]")

    console.print("\n[bold]tail-deferred (settled)[/bold]")
    console.print(f"[cyan]{BANNER}[/cyan]")
    for line in TELEMETRY:
        console.print(f"[blue]{line}[/blue]")
    console.print("[dim]→ plan.md written[/dim]")

    console.print("\n[bold]below (settled)[/bold]")
    console.print(f"[cyan]{BANNER}[/cyan]")
    for line in TELEMETRY:
        console.print(f"[blue]{line}[/blue]")
    console.print("[dim]→ plan.md written[/dim]")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preview the waiting indicator designs for slice 04-02."
    )
    parser.add_argument(
        "--option",
        choices=("tail", "tail-deferred", "below", "all"),
        default="all",
    )
    parser.add_argument("--seconds", type=float, default=4.0)
    parser.add_argument("--glyph", choices=tuple(GLYPHS), default="dots")
    parser.add_argument(
        "--elapsed",
        action="store_true",
        help="Append elapsed seconds to the tail variants; below stays bare.",
    )
    parser.add_argument("--retry", action="store_true")
    args = parser.parse_args()

    console = Console(stderr=True)
    if not console.is_terminal:
        console.print(
            "[yellow]stderr is not a terminal, so the live region cannot animate "
            "here. Run this script directly in a terminal to see the effect; "
            "below are the settled layouts only.[/yellow]"
        )
        _print_static_settled_layout(console)
        return

    variants = {
        "tail": preview_tail,
        "tail-deferred": preview_tail_deferred,
        "below": preview_below,
    }
    selected = ("tail", "tail-deferred") if args.option == "all" else (args.option,)
    for option in selected:
        console.print("")
        console.print(f"[bold]=== {option} ===[/bold]")
        variants[option](console, args.seconds, args.glyph, args.elapsed, args.retry)

    console.print("")
    console.print(
        "[bold]Tell the Pathfinder which design (or variation) you want; the "
        "choice is recorded in the slice's Key Unknowns.[/bold]"
    )


if __name__ == "__main__":
    main()
