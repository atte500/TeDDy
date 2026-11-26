"""Integration: the production indicator drives rich's real ``Live`` region.

The unit suite injects a recording region, so it pins the wiring but never
exercises rich's own ``Live`` — a mistyped kwarg in the production factory would
leave the feature dead in a real terminal while every unit case stayed green.
This module binds ``create_indicator`` to a real region on an isolated console
and proves the runtime facts no double can: the transient line is actually
drawn, teardown leaves no stale region behind, and ``start`` does not redirect
the process-global streams.

The console writes to an in-memory stream with an explicit width, so the test
touches no terminal, reads no environment sizing, and leaks no bytes into
another suite's captured output.
"""

import io
import sys

from rich.console import Console

from teddy_executor.adapters.outbound.console_waiting_indicator import (
    SPINNER_FRAMES,
    create_indicator,
)

LABEL = "Waiting for pathfinder to respond..."
OTHER_LABEL = "Waiting for architect to respond..."


def _console() -> tuple[Console, io.StringIO]:
    stream = io.StringIO()
    return Console(file=stream, force_terminal=True, width=80), stream


def test_the_real_region_draws_the_line_without_redirecting_the_streams() -> None:
    console, stream = _console()
    indicator = create_indicator(console)
    stdout_before, stderr_before = sys.stdout, sys.stderr

    try:
        indicator.begin(LABEL)
    finally:
        indicator.end()

    drawn = stream.getvalue()

    # Assert: rich's own region rendered the label and a spinner glyph, so the
    # production factory's arguments are genuinely accepted.
    assert LABEL in drawn
    assert any(frame in drawn for frame in SPINNER_FRAMES)

    # Assert: redirection is unconditional in ``start``, so a wrong flag would
    # have swapped the process-global streams from the daemon worker.
    assert sys.stdout is stdout_before
    assert sys.stderr is stderr_before


def test_the_region_reopens_after_teardown() -> None:
    console, stream = _console()
    indicator = create_indicator(console)

    indicator.begin(LABEL)
    indicator.end()
    indicator.begin(OTHER_LABEL)
    indicator.end()

    drawn = stream.getvalue()

    # Assert: teardown forgets the region, so the next wait draws a new line
    # instead of returning early on a stale reference.
    assert LABEL in drawn
    assert OTHER_LABEL in drawn
