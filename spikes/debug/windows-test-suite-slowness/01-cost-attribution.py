"""Attribute suite wall-clock cost to concrete per-test mechanisms.

Counts how many tests request the pyfakefs ``fs`` fixture, the ``env`` harness,
and the ``openrouter_mock`` HTTP fixture, then measures the Windows cost of a
subprocess spawn and a pyfakefs patch cycle so the dominant term is explicit.
"""

import ast
import platform
import subprocess
import sys
import time
from pathlib import Path

TESTS_ROOT = Path("tests")
FIXTURES = ("fs", "env", "real_env", "container", "openrouter_mock", "httpserver")


def test_functions_requesting(argument: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in TESTS_ROOT.rglob("test_*.py"):
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            args = [a.arg for a in node.args.args]
            args += [a.arg for a in node.args.kwonlyargs]
            if argument in args:
                counts[str(path)] = counts.get(str(path), 0) + 1
    return counts


def measure_patcher_cycle(count: int = 5) -> None:
    from pyfakefs.fake_filesystem_unittest import Patcher

    start = time.perf_counter()
    for _ in range(count):
        patcher = Patcher()
        patcher.setUp()
        try:
            Path("probe.txt").write_text("x")
        finally:
            patcher.tearDown()
    total = time.perf_counter() - start
    print(f"pyfakefs Patcher cycle: {total / count * 1000:.0f} ms/cycle over {count}")


def measure_spawn(label: str, command: list[str], count: int = 20) -> None:
    start = time.perf_counter()
    for _ in range(count):
        subprocess.run(command, capture_output=True, check=False)
    total = time.perf_counter() - start
    print(f"{label}: {total / count * 1000:.1f} ms/spawn over {count}")


def main() -> None:
    print(f"python: {sys.version.split()[0]}")
    print(f"platform: {platform.platform()}")

    for fixture_name in FIXTURES:
        counts = test_functions_requesting(fixture_name)
        print(f"tests requesting {fixture_name}: {sum(counts.values())}")
        for path in sorted(counts, key=lambda p: -counts[p])[:5]:
            print(f"    {counts[path]:4d}  {path}")

    measure_spawn("cmd /c echo", ["cmd", "/c", "echo", "x"])
    measure_spawn("python -c pass", [sys.executable, "-c", "pass"], count=10)
    measure_patcher_cycle()


if __name__ == "__main__":
    main()