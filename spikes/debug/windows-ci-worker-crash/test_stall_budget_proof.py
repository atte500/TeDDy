"""Controlled experiment: a transient host stall against the per-test budget.

Run explicitly. The default suite skips ``spikes`` through ``norecursedirs``.
The twenty second sleep stands in for a transient stall on a contended CI
runner. Under the ``thread`` timeout method it kills the xdist worker when the
budget is 15 seconds and passes when the budget exceeds the stall, so the
experiment shows that the budget, not the victim test, decides the outcome.
"""

import time


def test_transient_stall_survives_a_generous_budget() -> None:
    print("STALL_START", flush=True)
    time.sleep(20)
    print("STALL_END", flush=True)