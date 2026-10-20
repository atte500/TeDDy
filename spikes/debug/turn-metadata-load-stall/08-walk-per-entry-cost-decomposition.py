"""Decompose the per-entry cost inside walk_recursive.

Probe 07 attributed the 0.157s generator cost to the walk (0.109s for 896
entries) and only 0.028s to the formatter, so the per-entry work inside
``walk_recursive`` is the remaining unknown. Each entry pays a ``Path``
construction with ``relative_to``, two separate stat syscalls
(``os.path.isdir`` and ``os.path.islink``), and a pathspec ``match_file``
call. This probe accumulates each component's cost in a faithful replica,
then compares the production double-stat approach with ``DirEntry``'s cached
``is_dir(follow_symlinks=False)`` and ``is_symlink()`` methods, and it
verifies that both walks yield the identical path set with identical
directory flags.
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path("src").resolve()))

from teddy_executor.adapters.outbound.filesystem_helpers import walk_recursive
from teddy_executor.adapters.outbound.local_repo_tree_generator import (
    LocalRepoTreeGenerator,
)


def timed(label: str, function):
    """Run a callable, print its wall-clock cost, and return its result."""
    start = time.perf_counter()
    result = function()
    print(f"{label}: {time.perf_counter() - start:.4f}s")
    return result


def production_walk(root: Path, spec) -> list[tuple[Path, bool]]:
    """Collect the production walk's entries for comparison."""
    return [(entry, is_dir) for entry, is_dir in walk_recursive(root, root, spec)]


def instrumented_walk(root: Path, spec) -> tuple[dict[str, float], list[tuple[Path, bool]]]:
    """Mirror the production walk while accumulating per-component cost."""
    buckets = {
        "path_and_relative": 0.0,
        "os_path_isdir": 0.0,
        "os_path_islink": 0.0,
        "spec_match_file": 0.0,
    }
    yielded: list[tuple[Path, bool]] = []

    def recurse(start_dir: Path) -> None:
        with os.scandir(str(start_dir)) as iterator:
            for entry in iterator:
                start = time.perf_counter()
                entry_path = Path(entry.path)
                try:
                    rel_path = entry_path.relative_to(root)
                except ValueError:
                    rel_path = entry_path
                buckets["path_and_relative"] += time.perf_counter() - start

                start = time.perf_counter()
                dir_flag = os.path.isdir(str(entry_path))
                buckets["os_path_isdir"] += time.perf_counter() - start

                start = time.perf_counter()
                link_flag = os.path.islink(str(entry_path))
                buckets["os_path_islink"] += time.perf_counter() - start

                is_real_dir = dir_flag and not link_flag
                rel_path_str = str(rel_path).replace("\\", "/")
                match_path = rel_path_str + "/" if is_real_dir else rel_path_str

                start = time.perf_counter()
                matched = spec.match_file(match_path)
                buckets["spec_match_file"] += time.perf_counter() - start

                if matched:
                    continue

                yielded.append((entry_path, is_real_dir))
                if is_real_dir:
                    recurse(entry_path)

    recurse(root)
    return buckets, yielded


def direntry_walk(root: Path, spec) -> list[tuple[Path, bool]]:
    """Replica walk that reads is_dir and is_symlink from the scan cache."""
    yielded: list[tuple[Path, bool]] = []

    def recurse(start_dir: Path) -> None:
        with os.scandir(str(start_dir)) as iterator:
            for entry in iterator:
                entry_path = Path(entry.path)
                try:
                    rel_path = entry_path.relative_to(root)
                except ValueError:
                    rel_path = entry_path

                is_real_dir = (
                    entry.is_dir(follow_symlinks=False) and not entry.is_symlink()
                )
                rel_path_str = str(rel_path).replace("\\", "/")
                match_path = rel_path_str + "/" if is_real_dir else rel_path_str

                if spec.match_file(match_path):
                    continue

                yielded.append((entry_path, is_real_dir))
                if is_real_dir:
                    recurse(entry_path)

    recurse(root)
    return yielded


def list_directory_entries(directory: Path) -> list[os.DirEntry]:
    """List a directory's entries and close the scan iterator."""
    with os.scandir(str(directory)) as iterator:
        return list(iterator)


def main() -> None:
    generator = LocalRepoTreeGenerator()
    root = generator.root_dir
    spec = generator.ignore_spec
    print("root", root)

    production = timed("production walk_recursive", lambda: production_walk(root, spec))
    print("production entries", len(production))
    print("production dirs", len([path for path, is_dir in production if is_dir]))

    start = time.perf_counter()
    buckets, instrumented = instrumented_walk(root, spec)
    instrumented_total = time.perf_counter() - start
    print(f"instrumented walk total: {instrumented_total:.4f}s")
    for name, seconds in buckets.items():
        print(f"  component {name}: {seconds:.4f}s")
    print(f"  component sum: {sum(buckets.values()):.4f}s")
    print(
        f"  unaccounted (scandir, recursion, set work): "
        f"{instrumented_total - sum(buckets.values()):.4f}s"
    )
    print("instrumented entries", len(instrumented))

    replica = timed(
        "replica walk (DirEntry cached stat)", lambda: direntry_walk(root, spec)
    )
    print("replica entries", len(replica))

    production_map = {path: is_dir for path, is_dir in production}
    replica_map = {path: is_dir for path, is_dir in replica}
    print("identical path set", set(production_map) == set(replica_map))
    print("identical dir flags", production_map == replica_map)

    directories = [root] + [path for path, is_dir in production if is_dir]
    listed = timed(
        f"os.scandir listing over {len(directories)} dirs",
        lambda: [list_directory_entries(directory) for directory in directories],
    )
    print("directories listed", len(listed))

    timed("production generate_tree", generator.generate_tree)
    timed("production generate_tree (repeat)", generator.generate_tree)


if __name__ == "__main__":
    main()