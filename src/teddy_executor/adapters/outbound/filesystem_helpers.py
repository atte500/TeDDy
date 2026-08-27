import os
from pathlib import Path
from typing import Any, Iterator, Tuple


def load_ignore_spec(root_dir: Path) -> Any:
    """
    Loads and returns a pathspec for ignores (.gitignore and .teddyignore).
    Uses os.path functions (patched by pyfakefs) instead of Path methods.
    """
    import pathspec

    default_ignores = {
        ".git/",
        ".venv/",
        "__pycache__/",
        ".teddy/",
        ".ruff_cache/",
    }
    lines = list(default_ignores)

    gitignore_path = root_dir / ".gitignore"
    # FIX: Use os.path.isfile (pyfakefs patches this) instead of Path.is_file()
    if os.path.isfile(str(gitignore_path)):
        lines.append(gitignore_path.name)
        # FIX: Use open() (pyfakefs patches this) instead of Path.read_text()
        with open(str(gitignore_path), "r", encoding="utf-8") as f:
            lines.extend(f.read().splitlines())

    teddyignore_path = root_dir / ".teddyignore"
    if os.path.isfile(str(teddyignore_path)):
        lines.append(teddyignore_path.name)
        with open(str(teddyignore_path), "r", encoding="utf-8") as f:
            lines.extend(f.read().splitlines())

    return pathspec.PathSpec.from_lines("gitwildmatch", lines)


def walk_recursive(
    root_dir: Path,
    start_dir: Path,
    spec: Any,
) -> Iterator[Tuple[Path, bool]]:
    """
    Recursively walks a directory, yielding (Path, is_dir) for non-ignored entries.
    Uses os.path functions (patched by pyfakefs) for filesystem checks.
    Yielded paths are Path objects for compatibility with callers.
    """
    # FIX: Use os.scandir (pyfakefs patches this) instead of iterdir()
    try:
        scandir_iter = os.scandir(str(start_dir))
    except PermissionError:
        return

    for entry in scandir_iter:
        entry_path = Path(entry.path)
        try:
            rel_path = entry_path.relative_to(root_dir)
        except ValueError:
            # Fallback for paths outside root (e.g. symlinks)
            rel_path = entry_path

        rel_path_str = str(rel_path).replace("\\", "/")
        # FIX: Use os.path.isdir and os.path.islink (pyfakefs patches these)
        is_real_dir = os.path.isdir(str(entry_path)) and not os.path.islink(
            str(entry_path)
        )

        # For directories, add a trailing slash to match gitignore behavior
        match_path = rel_path_str + "/" if is_real_dir else rel_path_str

        if spec.match_file(match_path):
            continue

        yield entry_path, is_real_dir

        if is_real_dir:
            yield from walk_recursive(root_dir, entry_path, spec)

    scandir_iter.close()
