from pathlib import Path
from typing import Any, Iterator, Tuple


def load_ignore_spec(root_dir: Path) -> Any:
    """
    Loads and returns a pathspec for ignores (.gitignore and .teddyignore).
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
    if gitignore_path.is_file():
        lines.append(gitignore_path.name)
        lines.extend(gitignore_path.read_text(encoding="utf-8").splitlines())

    teddyignore_path = root_dir / ".teddyignore"
    if teddyignore_path.is_file():
        lines.append(teddyignore_path.name)
        lines.extend(teddyignore_path.read_text(encoding="utf-8").splitlines())

    return pathspec.PathSpec.from_lines("gitwildmatch", lines)


def walk_recursive(
    root_dir: Path,
    start_dir: Path,
    spec: Any,
) -> Iterator[Tuple[Path, bool]]:
    """
    Recursively walks a directory, yielding (Path, is_dir) for non-ignored entries.
    Yielded paths are absolute.
    """
    for entry in start_dir.iterdir():
        try:
            rel_path = entry.relative_to(root_dir)
        except ValueError:
            # Fallback for paths outside root (e.g. symlinks)
            rel_path = entry

        rel_path_str = str(rel_path).replace("\\", "/")
        is_real_dir = entry.is_dir() and not entry.is_symlink()

        # For directories, add a trailing slash to match gitignore behavior
        match_path = rel_path_str + "/" if is_real_dir else rel_path_str

        if spec.match_file(match_path):
            continue

        yield entry, is_real_dir

        if is_real_dir:
            yield from walk_recursive(root_dir, entry, spec)
