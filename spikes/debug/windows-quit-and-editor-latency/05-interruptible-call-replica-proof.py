"""Prove the polling fix for the Windows deferred-SIGINT wait.

Runs the same self-delivered quit measurement against the sandbox replica of
``run_interruptible``. A prompt interrupt near the fire delay instead of the
worker duration proves the fix without touching production code.
"""

from __future__ import annotations

import importlib.util
import signal
import sys
import threading
import time
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "src"))

from teddy_executor.core.utils.interrupt_guard import InterruptGuard, raise_interrupt

FIRE_DELAY_SECONDS = 0.3
WORK_SECONDS = 1.5


def _load_replica() -> ModuleType:
    """Load the sandbox replica module from its file path."""
    spec = importlib.util.spec_from_file_location(
        "replica_interruptible_call", HERE / "replica_interruptible_call.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load replica module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _measure(run_interruptible) -> dict[str, object]:
    """Run one self-delivered quit against the given wait and report latency."""
    guard = InterruptGuard(monotonic=time.monotonic)
    previous = guard.install()

    def fire() -> None:
        time.sleep(FIRE_DELAY_SECONDS)
        guard.record_source("q")
        raise_interrupt()

    threading.Thread(target=fire, daemon=True).start()
    started = time.perf_counter()
    outcome = "completed"
    try:
        try:
            with guard.enter_waiting():
                run_interruptible(lambda: time.sleep(WORK_SECONDS))
        except KeyboardInterrupt:
            outcome = "interrupted"
        finally:
            signal.signal(signal.SIGINT, previous)
    except KeyboardInterrupt:
        outcome = "interrupted-after-finally"
    return {
        "scenario": "replica_future_polling",
        "outcome": outcome,
        "latency_s": round(time.perf_counter() - started, 3),
        "fire_at_s": FIRE_DELAY_SECONDS,
        "work_s": WORK_SECONDS,
        "source": guard.source,
    }


def main() -> int:
    """Measure the replica wait and print the result row."""
    replica = _load_replica()
    print(f"platform={sys.platform}", flush=True)
    print(dict(_measure(replica.run_interruptible)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())