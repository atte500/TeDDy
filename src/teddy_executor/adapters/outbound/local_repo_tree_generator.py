import os
from pathlib import Path
from typing import Any
from teddy_executor.core.ports.outbound.repo_tree_generator import IRepoTreeGenerator


class _RecursiveListFormatter:
    """
    A helper class to format a set of paths into a recursive "ls -R" style list.
    """

    def __init__(self, root_dir: Path, included_paths: set[Path]):
        self.root_dir = root_dir
        self.included_paths = included_paths

    def format(self) -> str:
        """Generates the recursive list string."""
        sections: list[str] = []
        # Gather all directories that are included (including root)
        directories = sorted(
            [p for p in self.included_paths if p.is_dir() and not p.is_symlink()]
            + [self.root_dir],
            key=lambda p: str(p.relative_to(self.root_dir)).lower(),
        )

        for directory in directories:
            section_content = self._format_section(directory)
            if section_content:
                sections.append(section_content)

        return "\n\n".join(sections)

    def _format_section(self, directory: Path) -> str:
        """Formats a single directory section."""
        children = sorted(
            [p for p in directory.iterdir() if p in self.included_paths],
            key=lambda p: p.name.lower(),
        )

        if not children:
            return ""

        lines = []
        if directory != self.root_dir:
            rel_path = directory.relative_to(self.root_dir)
            # Poka-Yoke: Always use forward slashes for the tree protocol
            posix_rel_path = str(rel_path).replace(os.sep, "/")
            lines.append(f"./{posix_rel_path}:")

        for child in children:
            lines.append(child.name)

        return "\n".join(lines)


class LocalRepoTreeGenerator(IRepoTreeGenerator):
    """
    An adapter that generates a file tree for the local repository,
    respecting .gitignore and .teddyignore rules.
    """

    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir).resolve()
        self.ignore_spec = self._load_ignore_spec()

    def _load_ignore_spec(self) -> Any:
        """Loads ignore files."""
        import pathspec

        default_ignores = {".git/", ".venv/", "__pycache__/", ".teddy/", ".ruff_cache/"}
        lines = list(default_ignores)
        gitignore_path = self.root_dir / ".gitignore"
        if gitignore_path.is_file():
            lines.append(gitignore_path.name)
            lines.extend(gitignore_path.read_text(encoding="utf-8").splitlines())

        teddyignore_path = self.root_dir / ".teddyignore"
        if teddyignore_path.is_file():
            lines.append(teddyignore_path.name)
            lines.extend(teddyignore_path.read_text(encoding="utf-8").splitlines())

        return pathspec.PathSpec.from_lines("gitwildmatch", lines)

    def _get_included_paths(self) -> set[Path]:
        """
        Walks the directory and returns a set of all files and parent directories
        that are not excluded by the ignore spec.
        """
        included_paths: set[Path] = set()
        self._walk(self.root_dir, included_paths)
        return included_paths

    def _walk(self, current_dir: Path, included_paths: set[Path]):
        """
        Recursively walks the directory tree, pruning ignored directories.
        """
        for entry in current_dir.iterdir():
            relative_path_str = str(entry.relative_to(self.root_dir))
            # We treat symlinks as files to avoid infinite recursion
            is_real_dir = entry.is_dir() and not entry.is_symlink()

            # For directories, add a trailing slash to match gitignore behavior
            match_path = relative_path_str + "/" if is_real_dir else relative_path_str

            if self.ignore_spec.match_file(match_path):
                continue

            # If not ignored, add to set
            included_paths.add(entry)

            # Ensure parent connectivity
            for parent in entry.parents:
                if parent == self.root_dir:
                    break
                included_paths.add(parent)

            # Recurse if it's a directory
            if is_real_dir:
                self._walk(entry, included_paths)

    def generate_tree(self) -> str:
        """
        Generates a string representation of the file tree by gathering paths
        and then delegating to a formatter.
        """
        included_paths = self._get_included_paths()
        formatter = _RecursiveListFormatter(self.root_dir, included_paths)
        return formatter.format()
