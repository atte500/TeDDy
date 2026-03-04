import pathspec
from pathlib import Path
from teddy_executor.core.ports.outbound.repo_tree_generator import IRepoTreeGenerator


class _IndentedListFormatter:
    """
    A helper class to format a set of paths into a simple, indented list
    that is reliable and easy for an LLM to parse.
    """

    def __init__(self, root_dir: Path, included_paths: set[Path]):
        self.root_dir = root_dir
        self.included_paths = included_paths

    def format(self) -> str:
        """Generates the indented list string."""
        tree_lines: list[str] = []
        # Start the recursion from the root's children at level 0
        self._format_recursive(self.root_dir, 0, tree_lines)
        return "\n".join(tree_lines)

    def _format_recursive(self, directory: Path, level: int, tree_lines: list[str]):
        """Recursively builds the tree string."""
        children = sorted(
            [p for p in directory.iterdir() if p in self.included_paths],
            key=lambda p: (not p.is_dir(), p.name.lower()),
        )

        indent = "  " * level
        for path in children:
            entry = f"{path.name}/" if path.is_dir() else path.name
            tree_lines.append(f"{indent}{entry}")

            if path.is_dir():
                self._format_recursive(path, level + 1, tree_lines)


class LocalRepoTreeGenerator(IRepoTreeGenerator):
    """
    An adapter that generates a file tree for the local repository,
    respecting .gitignore and .teddyignore rules.
    """

    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir).resolve()
        self.ignore_spec = self._load_ignore_spec()

    def _load_ignore_spec(self) -> pathspec.PathSpec:
        """Loads ignore files."""
        default_ignores = {".git/", ".venv/", "__pycache__/", ".teddy/", ".ruff_cache/"}
        lines = list(default_ignores)
        gitignore_path = self.root_dir / ".gitignore"
        if gitignore_path.is_file():
            lines.append(gitignore_path.name)
            lines.extend(gitignore_path.read_text().splitlines())

        teddyignore_path = self.root_dir / ".teddyignore"
        if teddyignore_path.is_file():
            lines.append(teddyignore_path.name)
            lines.extend(teddyignore_path.read_text().splitlines())

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
            # For directories, add a trailing slash to match gitignore behavior
            match_path = (
                relative_path_str + "/" if entry.is_dir() else relative_path_str
            )

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
            if entry.is_dir():
                self._walk(entry, included_paths)

    def generate_tree(self) -> str:
        """
        Generates a string representation of the file tree by gathering paths
        and then delegating to a formatter.
        """
        included_paths = self._get_included_paths()
        formatter = _IndentedListFormatter(self.root_dir, included_paths)
        return formatter.format()
