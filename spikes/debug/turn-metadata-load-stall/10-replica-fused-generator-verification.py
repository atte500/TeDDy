"""Verify the fused tree-generator replica against the production adapter.

Probe 09 proved a standalone fused function reproduces the production output.
This script exercises the same traversal through the adapter surface by
importing the sandbox replica and comparing it with the production class. The
The real repository covers scale. The synthetic tree covers empty directories,
nested ignore patterns, a second ignore file, a best-effort directory symlink,
and directory names that sort below the `.` root key, so section ordering
parity against the production formatter is pinned.
"""

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from teddy_executor.adapters.outbound.local_repo_tree_generator import (  # noqa: E402
    LocalRepoTreeGenerator as ProductionGenerator,
)
from replica_local_repo_tree_generator import (  # noqa: E402
    LocalRepoTreeGenerator as ReplicaGenerator,
)


def timed(label: str, function):
    """Run a callable, print its wall-clock cost, and return its result."""
    start = time.perf_counter()
    result = function()
    print(f"{label}: {time.perf_counter() - start:.4f}s")
    return result


def build_synthetic_tree() -> Path:
    """Create a tree that stresses ordering, ignores, and empty directories."""
    root = Path(tempfile.mkdtemp(prefix="teddy-fused-verify-"))
    (root / ".gitignore").write_text(".venv/\n*.log\n", encoding="utf-8")
    (root / ".teddyignore").write_text("secret.md\n", encoding="utf-8")
    (root / "!important").mkdir()
    (root / "!important" / "top.txt").touch()
    (root / "#hash").mkdir()
    (root / "#hash" / "file.txt").touch()
    (root / "Alpha.txt").touch()
    (root / "beta.TXT").touch()
    (root / "visible.txt").touch()
    (root / "debug.log").touch()
    (root / "secret.md").touch()
    src = root / "src"
    src.mkdir()
    (src / "main.py").touch()
    nested = src / "nested" / "deep"
    nested.mkdir(parents=True)
    (nested / "file.txt").touch()
    (root / "docs").mkdir()
    (root / "docs" / "guide.md").touch()
    (root / "docs" / "empty").mkdir()
    deep = root / "a" / "b" / "c"
    deep.mkdir(parents=True)
    (deep / "file.txt").touch()
    ignored = root / ".venv"
    ignored.mkdir()
    for index in range(500):
        (ignored / f"file_{index}.py").touch()
    try:
        os.symlink(root / "docs", root / "link_to_docs", target_is_directory=True)
    except (OSError, NotImplementedError):
        print("symlink creation unavailable on this host")
    return root


def compare(label: str, root: Path) -> None:
    """Assert byte equality between production and replica on one tree."""
    production = ProductionGenerator(root_dir=str(root))
    replica = ReplicaGenerator(root_dir=str(root))
    expected = timed(f"{label}: production", production.generate_tree)
    actual = timed(f"{label}: replica", replica.generate_tree)
    print(
        f"{label}: lines {len(expected.splitlines())}, "
        f"identical {expected == actual}"
    )
    if expected != actual:
        expected_lines = expected.splitlines()
        actual_lines = actual.splitlines()
        for index, (left, right) in enumerate(zip(expected_lines, actual_lines)):
            if left != right:
                print(f"  first difference at line {index}: production={left!r} replica={right!r}")
                break
        print("  production length", len(expected_lines), "replica length", len(actual_lines))
        raise AssertionError(f"{label} output differs between production and replica")
    timed(f"{label}: production (repeat)", production.generate_tree)
    timed(f"{label}: replica (repeat)", replica.generate_tree)


def main() -> None:
    compare("repo", Path(".").resolve())
    synthetic = build_synthetic_tree()
    try:
        compare("synthetic", synthetic.resolve())
    finally:
        shutil.rmtree(synthetic, ignore_errors=True)


if __name__ == "__main__":
    main()