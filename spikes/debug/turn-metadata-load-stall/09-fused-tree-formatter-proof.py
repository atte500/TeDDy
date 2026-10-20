"""Prove tree-formatter variants reproduce the generator byte for byte.

Probe 08 showed the production walk spends 0.0455s on ``Path`` construction
plus ``relative_to``, 0.0319s on pathspec matching, and only 0.0156s on the two
``os.path`` stat syscalls, so the cached-stat replica saved just 11%. Two
candidate fixes remain. The dict-formatter variant keeps the production walk
but formats from a path-to-is_dir map, removing the formatter's second
filesystem pass. The fused variant threads relative path strings, reads the
directory and symlink flags from the ``DirEntry`` scan cache, and builds the
formatted sections during one pass. This probe checks byte-for-byte output
equality against the real generator on the real repository and on a synthetic
tree, then compares wall-clock cost.
"""

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path("src").resolve()))

from teddy_executor.adapters.outbound.filesystem_helpers import (
    load_ignore_spec,
    walk_recursive,
)
from teddy_executor.adapters.outbound.local_repo_tree_generator import (
    LocalRepoTreeGenerator,
)


def timed(label: str, function):
    """Run a callable, print its wall-clock cost, and return its result."""
    start = time.perf_counter()
    result = function()
    print(f"{label}: {time.perf_counter() - start:.4f}s")
    return result


def dict_formatter_tree(root: Path, spec) -> str:
    """Reuse the production walk but format from a path-to-is_dir map."""
    included: dict[Path, bool] = {}
    for entry, is_dir in walk_recursive(root, root, spec):
        included[entry] = is_dir
        for parent in entry.parents:
            if parent == root:
                break
            included[parent] = True

    children_by_parent: dict[Path, list[str]] = {}
    directories: list[Path] = [root]
    for path, is_dir in included.items():
        children_by_parent.setdefault(path.parent, []).append(path.name)
        if is_dir:
            directories.append(path)

    sections: list[str] = []
    for directory in sorted(
        directories, key=lambda p: str(p.relative_to(root)).lower()
    ):
        names = sorted(children_by_parent.get(directory, []), key=str.lower)
        if not names:
            continue
        if directory == root:
            sections.append("\n".join(names))
        else:
            rel = str(directory.relative_to(root)).replace(os.sep, "/")
            sections.append("\n".join([f"./{rel}:"] + names))
    return "\n\n".join(sections)


def fused_tree(root: Path, spec) -> str:
    """Walk once with threaded relative strings and format during the same pass."""
    sections: list[tuple[str, str, list[str]]] = []

    def visit(directory: str, rel_posix: str) -> list[str]:
        names: list[str] = []
        try:
            with os.scandir(directory) as iterator:
                entries = list(iterator)
        except PermissionError:
            return names

        for entry in entries:
            is_real_dir = (
                entry.is_dir(follow_symlinks=False) and not entry.is_symlink()
            )
            child_rel = f"{rel_posix}/{entry.name}" if rel_posix else entry.name
            match_path = child_rel + "/" if is_real_dir else child_rel
            if spec.match_file(match_path):
                continue

            names.append(entry.name)
            if is_real_dir:
                child_names = visit(entry.path, child_rel)
                sort_key = child_rel.replace("/", os.sep).lower()
                sections.append((sort_key, child_rel, child_names))

        names.sort(key=str.lower)
        return names

    root_names = visit(str(root), "")
    sections.append((".", "", root_names))
    sections.sort(key=lambda item: item[0])

    rendered: list[str] = []
    for _key, display_rel, names in sections:
        if not names:
            continue
        if display_rel:
            rendered.append("\n".join([f"./{display_rel}:"] + names))
        else:
            rendered.append("\n".join(names))
    return "\n\n".join(rendered)


def build_synthetic_tree() -> Path:
    """Create a tree that exercises empty directories, nesting, and ignore rules."""
    root = Path(tempfile.mkdtemp(prefix="teddy-tree-probe-"))
    (root / ".gitignore").write_text(".venv/\n*.log\n", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "main.py").touch()
    (root / "docs").mkdir()
    (root / "docs" / "guide.md").touch()
    (root / "empty").mkdir()
    nested = root / "a" / "b" / "c"
    nested.mkdir(parents=True)
    (nested / "file.txt").touch()
    (root / ".venv").mkdir()
    (root / ".venv" / "lib.py").touch()
    (root / "debug.log").touch()
    return root


def compare(label: str, root: Path) -> None:
    """Compare the real generator against both replicas on one tree."""
    resolved = root.resolve()
    real_generator = LocalRepoTreeGenerator(root_dir=str(resolved))
    real = timed(f"{label}: real generate_tree", real_generator.generate_tree)
    print(f"{label}: real lines", len(real.splitlines()))

    spec = load_ignore_spec(resolved)

    dict_first = timed(
        f"{label}: dict-formatter variant",
        lambda: dict_formatter_tree(resolved, spec),
    )
    print(f"{label}: dict-formatter identical output", real == dict_first)

    fused_first = timed(
        f"{label}: fused variant", lambda: fused_tree(resolved, spec)
    )
    print(f"{label}: fused identical output", real == fused_first)

    if real != fused_first:
        real_lines = real.splitlines()
        fused_lines = fused_first.splitlines()
        for index, (left, right) in enumerate(zip(real_lines, fused_lines)):
            if left != right:
                print(f"  first difference at line {index}: real={left!r} fused={right!r}")
                break
        print("  real length", len(real_lines), "fused length", len(fused_lines))

    timed(f"{label}: real generate_tree (repeat)", real_generator.generate_tree)
    timed(
        f"{label}: dict-formatter variant (repeat)",
        lambda: dict_formatter_tree(resolved, spec),
    )
    timed(f"{label}: fused variant (repeat)", lambda: fused_tree(resolved, spec))


def main() -> None:
    compare("repo", Path("."))

    synthetic = build_synthetic_tree()
    try:
        compare("synthetic", synthetic)
    finally:
        shutil.rmtree(synthetic, ignore_errors=True)


if __name__ == "__main__":
    main()