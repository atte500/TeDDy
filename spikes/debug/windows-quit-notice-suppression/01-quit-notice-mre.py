"""MRE: pressing `q` must print the interrupt notice on Windows.

Production path under test:
``TerminalQuitKeyListener`` reader thread -> ``on_quit`` ->
``container._record_quit_source`` -> ``InterruptGuard.record_source("q")`` ->
SIGINT self-delivery -> ``InterruptGuard._handle_signal`` ->
``KeyboardInterrupt`` -> boundary notice.

On Windows the production self-delivery uses ``os.kill``, which calls
``TerminateProcess`` for SIGINT. The process dies before the notice. The
``fixed`` scenario uses the sandbox replica's ``signal.raise_signal`` delivery.

Usage:
    python 01-quit-notice-mre.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

CHILD = textwrap.dedent(
    '''
    import sys
    import threading
    import time

    from teddy_executor.core.utils.interrupt_guard import InterruptGuard
    from teddy_executor.core.utils.session_notices import format_interrupt_notice

    mode = sys.argv[1]
    delivery = sys.argv[2]

    class _GuardContainer:
        """Minimal container seam: resolve(InterruptGuard) -> the shared guard."""

        def __init__(self, guard):
            self._guard = guard

        def resolve(self, _service):
            return self._guard

    if delivery == "fixed":
        from replica_interrupt_guard import raise_interrupt

        def record_quit_source(container):
            container.resolve(InterruptGuard).record_source("q")
            raise_interrupt()
    else:
        from teddy_executor.container import _record_quit_source as record_quit_source

    guard = InterruptGuard(monotonic=time.monotonic)
    guard.install()
    container = _GuardContainer(guard)

    try:
        if mode == "threaded":
            worker = threading.Thread(
                target=lambda: record_quit_source(container), name="quit-reader"
            )
            worker.start()
            worker.join()
            time.sleep(0.2)
        else:
            record_quit_source(container)
    except KeyboardInterrupt:
        print("NOTICE: " + format_interrupt_notice(guard.source), flush=True)
        raise SystemExit(0)

    print("NO_NOTICE (guard.interrupted=%s)" % guard.interrupted.is_set(), flush=True)
    raise SystemExit(3)
    '''
)


def _run(mode: str, delivery: str) -> subprocess.CompletedProcess[str]:
    script_dir = str(Path(__file__).resolve().parent)
    env = dict(os.environ)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        script_dir if not existing else script_dir + os.pathsep + existing
    )
    return subprocess.run(
        [sys.executable, "-c", CHILD, mode, delivery],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )


def main() -> int:
    print("platform=%s" % sys.platform)
    failed = False
    for delivery in ("production", "fixed"):
        for mode in ("direct", "threaded"):
            result = _run(mode, delivery)
            output = (result.stdout + result.stderr).strip() or "(no output)"
            print("--- %s/%s rc=%s" % (delivery, mode, result.returncode))
            for line in output.splitlines():
                print("    " + line)
            if delivery == "production" and sys.platform == "win32":
                if result.returncode == 2 and result.stdout.strip() == "":
                    print("    REPRODUCED: process terminated without a notice")
            if delivery == "fixed":
                if (
                    result.returncode != 0
                    or "Interrupted by user (q)" not in result.stdout
                ):
                    failed = True
                    print("    FAILED: the notice was not printed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())