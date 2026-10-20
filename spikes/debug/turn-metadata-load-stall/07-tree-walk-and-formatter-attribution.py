"""Attribute the repository tree cost to the walk or the formatter.

Probe 06 showed the real generator costs 0.159-0.165s, but reading
``walk_recursive`` proves it prunes ignored directories during descent. This
probe counts the real walk's yielded entries, lists which top-level
directories the ignore spec prunes, and times the walk, ``_get_included_paths``,
the formatter's stat-and-sort pass, its per-directory ``iterdir`` scans, and a
full ``format`` separately, so the 0.159s is attributed to the walk or the
formatter with no ambiguity.
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path("src").resolve()))

from teddy_executor.adapters.outbound.filesystem_helpers import (
    load_ignore_spec,
    walk_recursive,
)
from teddy_executor.adapters.outbound.local_repo_tree_generator import (
    LocalRepoTreeGenerator,
    _RecursiveListFormatter,
)


def timed(label: str, function):
    """Run a callable, print its wall-clock cost, and return its result."""
    start = time.perf_counter()
    result = function()
    print(f"{label}: {time.perf_counter() - start:.3f}s")
    return result


def main() -> None:
    generator = LocalRepoTreeGenerator()
    spec = generator.ignore_spec
    root = generator.root_dir
    print("root", root)

    skipped_top: list[str] = []
    walked_top: list[str] = []
    for name in sorted(os.listdir(root)):
        candidate = root / name
        if candidate.is_dir() and not candidate.is_symlink():
            rel = str(candidate.relative_to(root)).replace("\\", "/") + "/"
            if spec.match_file(rel):
                skipped_top.append(name)
            else:
                walked_top.append(name)
    print("top-level pruned dirs", skipped_top)
    print("top-level walked dirs", walked_top)

    entries: list[tuple[Path, bool]] = []

    def collect() -> None:
        for entry, is_dir in walk_recursive(root, root, spec):
            entries.append((entry, is_dir))

    timed("walk_recursive total", collect)
    print("yielded entries", len(entries))
    print("yielded dirs", len([e for e, d in entries if d]))

    included = timed("_get_included_paths", generator._get_included_paths)
    print("included paths", len(included))

    def build_dirs() -> list[Path]:
        return sorted(
            [p for p in included if p.is_dir() and not p.is_symlink()] + [root],
            key=lambda p: str(p.relative_to(root)).lower(),
        )

    directories = timed("formatter directory stat+sort", build_dirs)
    print("directories formatted", len(directories))

    def iterdir_all() -> int:
        total = 0
        for directory in directories:
            total += len([p for p in directory.iterdir() if p in included])
        return total

    timed("formatter iterdir scans", iterdir_all)
    timed("full format", lambda: _RecursiveListFormatter(root, included).format())
    timed("generate_tree", generator.generate_tree)


if __name__ == "__main__":
    main()