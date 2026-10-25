"""Controlled experiment: what a pytest-timeout thread-method kill looks like.

Run explicitly. Not collected by the default suite because `spikes` is in
`norecursedirs`. Prints a marker, then sleeps past the configured timeout so
the `thread` timeout method calls `os._exit(1)` from its timer thread.
"""

import time


def test_prints_marker_then_hangs() -> None:
    print("BEFORE_HANG_MARKER", flush=True)
    time.sleep(60)