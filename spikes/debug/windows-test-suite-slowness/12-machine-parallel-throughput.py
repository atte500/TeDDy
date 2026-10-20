"""Measure this host's own pure-Python parallel throughput curve.

Probe 11 showed the suite keeps about seven logical processors busy yet
reaches only 3.42x over the serial run, and the worker curve never improves
past eight workers. Every suite measurement so far is relative to this host,
so none of them can say whether 3.3x is a suite defect or a hardware
ceiling. This probe supplies the missing absolute reference by running
independent single-threaded CPU-bound Python processes, releasing them
together behind a barrier, and reporting aggregate work per second.

A machine curve that also plateaus near 3.3x means the suite already
extracts the full machine capacity, so the macOS gap is hardware capacity
and per-core speed. A machine curve that keeps scaling past 3.3x means the
suite leaves real capacity unused and the investigation returns to the
suite with a measured target.
"""

import multiprocessing as mp
import os
import platform
import threading
import time

PROCESS_COUNTS = (1, 2, 3, 4, 6, 8, 10, 12)
REPEATS = 2
ITERATIONS = 2_000_000

# Suite wall clocks already recorded in the case file by probes 10 and 11.
# They are printed beside the machine curve so both efficiencies are read
# from one table.
SUITE_SECONDS = {
    1: 93.65,
    2: 56.53,
    4: 35.12,
    6: 36.95,
    8: 28.70,
    12: 29.35,
}


def burn(iterations: int) -> int:
    """Sum squares, the same workload shape as the single-core benchmark."""
    total = 0
    for index in range(iterations):
        total += index * index
    return total


def worker(barrier, results, iterations: int) -> None:
    """Wait for the joint start, then time one CPU-bound run."""
    barrier.wait(timeout=60)
    start = time.perf_counter()
    total = burn(iterations)
    end = time.perf_counter()
    results.put((start, end, total))


def run_config(count: int, iterations: int = ITERATIONS) -> tuple[float, float]:
    """Run `count` processes that start together and report span and throughput."""
    barrier = mp.Barrier(count + 1)
    results = mp.Queue()
    processes = [
        mp.Process(target=worker, args=(barrier, results, iterations))
        for _ in range(count)
    ]
    for process in processes:
        process.start()
    try:
        barrier.wait(timeout=60)
    except threading.BrokenBarrierError:
        for process in processes:
            process.terminate()
        raise

    samples = [results.get(timeout=120) for _ in range(count)]
    for process in processes:
        process.join(timeout=30)

    span = max(end for _start, end, _total in samples) - min(
        start for start, _end, _total in samples
    )
    return span, count * iterations / span


def main() -> None:
    print("cpu_count", os.cpu_count())
    print("processor", platform.processor())
    print("python", platform.python_version())
    print("iterations per process", ITERATIONS)
    print("repeats per worker count", REPEATS)
    try:
        print("affinity logical cpus", len(os.sched_getaffinity(0)))
    except AttributeError:
        print("affinity logical cpus unavailable on this platform")

    # Warm the interpreter once so the first timed run does not pay for it.
    burn(50_000)

    rows: list[tuple[int, float, float]] = []
    single_throughput = 0.0
    for count in PROCESS_COUNTS:
        best_span = 0.0
        best_throughput = 0.0
        for _repeat in range(REPEATS):
            span, throughput = run_config(count)
            if throughput > best_throughput:
                best_throughput = throughput
                best_span = span
        if count == 1:
            single_throughput = best_throughput
        rows.append((count, best_span, best_throughput))
        print(f"  measured {count} processes: span {best_span:.3f}s")

    print()
    print(
        f"{'procs':>5} {'span_s':>8} {'work_per_s':>12} {'machine_x':>10} "
        f"{'suite_s':>8} {'suite_x':>8}"
    )
    for count, span, throughput in rows:
        machine_speedup = throughput / single_throughput
        suite_seconds = SUITE_SECONDS.get(count)
        if suite_seconds is None:
            print(
                f"{count:5d} {span:8.3f} {throughput:12.0f} {machine_speedup:10.2f}"
            )
            continue
        suite_speedup = SUITE_SECONDS[1] / suite_seconds
        print(
            f"{count:5d} {span:8.3f} {throughput:12.0f} {machine_speedup:10.2f} "
            f"{suite_seconds:8.2f} {suite_speedup:8.2f}"
        )

    print()
    for count, _span, throughput in rows:
        efficiency = (throughput / single_throughput) / count
        print(f"machine efficiency at {count} processes: {efficiency:.0%} of ideal")


if __name__ == "__main__":
    main()