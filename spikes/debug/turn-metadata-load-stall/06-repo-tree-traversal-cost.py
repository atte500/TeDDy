"""Size the repository tree walk against a pruned traversal.

Context assembly is dominated by the repository tree walk (0.156s) and the
git shell-out (0.038s). If the generator descends into ignored directory
trees and discards their entries afterwards, most of that time is spent on
paths that never reach the output. This probe compares the real generator
against a traversal that prunes ignored directories before descending, and
it reports entry counts so the gap separates per-entry latency from pure
over-visiting.
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path("src").resolve()))

from teddy_executor.adapters.outbound.local_repo_tree_generator import (
    LocalRepoTreeGenerator,
)

ROOT = Path(".").resolve()
IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    ".teddy",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".idea",
    "dist",
    "build",
    "site-packages",
}


def timed(label: str, function):
    """Run a callable, print its wall-clock cost, and return its result."""
    start = time.perf_counter()
    result = function()
    print(f"{label}: {time.perf_counter() - start:.3f}s")
    return result


def walk_all() -> int:
    """Count every entry in a traversal that descends everywhere."""
    total = 0
    for _dirpath, dirnames, filenames in os.walk(ROOT):
        total += len(dirnames) + len(filenames)
    return total


def walk_pruned() -> int:
    """Count every entry in a traversal that prunes ignored directories."""
    total = 0
    for _dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [name for name in dirnames if name not in IGNORED_DIRECTORIES]
        total += len(dirnames) + len(filenames)
    return total


def main() -> None:
    generator = LocalRepoTreeGenerator()
    tree = timed("generate_tree #1", generator.generate_tree)
    timed("generate_tree #2", generator.generate_tree)
    lines = tree.splitlines() if isinstance(tree, str) else []
    print("tree lines", len(lines))
    print("tree characters", len(tree) if isinstance(tree, str) else -1)
    print("all entries", timed("walk all", walk_all))
    print("pruned entries", timed("walk pruned", walk_pruned))


if __name__ == "__main__":
    main()