"""Measure the terminal-write and payload-write cost inside the stall window.

The warm pre-LLM window measures about 0.31s on this host, yet the report is a
perceptible stutter that is worse on Windows. The remaining unmeasured
components are the four Rich console writes that render the turn header and
the three telemetry lines, plus the 325KB ``input.md`` write. Both run through
the real composition root, so the timings match a live session.
"""

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path("src").resolve()))

from teddy_executor.container import create_container
from teddy_executor.core.ports.outbound import IFileSystemManager, IUserInteractor


def timed(label: str, function):
    """Run a callable, print its wall-clock cost, and return its result."""
    start = time.perf_counter()
    result = function()
    print(f"{label}: {time.perf_counter() - start:.3f}s")
    return result


def main() -> None:
    container = create_container()
    ui = container.resolve(IUserInteractor)
    file_system = container.resolve(IFileSystemManager)

    header = "\n[cyan][09] session-slug | Waiting for Debugger to respond...[/cyan]"
    telemetry = [
        "[blue]• Model:[/blue] [magenta]openrouter/~deepseek/deepseek-flash-latest:nitro[/magenta]",
        "[blue]• Context:[/blue] [magenta]120.9k / 160.0k tokens[/magenta]",
        "[blue]• Session Cost:[/blue] [magenta]$0.0223[/magenta]\n",
    ]

    for run in (1, 2, 3):
        total_start = time.perf_counter()
        timed(f"header write #{run}", lambda: ui.display_message(header))
        for index, line in enumerate(telemetry, start=1):
            timed(
                f"telemetry line {index} #{run}",
                lambda text=line: ui.display_message(text),
            )
        print(f"console total #{run}: {time.perf_counter() - total_start:.3f}s")

    payload = "x" * 325822
    target = Path(tempfile.mkdtemp(prefix="teddy-probe-write-")) / "input.md"
    timed(
        "write 325KB input.md (temp)",
        lambda: file_system.write_file(target.as_posix(), payload),
    )
    print("written bytes", target.stat().st_size)


if __name__ == "__main__":
    main()