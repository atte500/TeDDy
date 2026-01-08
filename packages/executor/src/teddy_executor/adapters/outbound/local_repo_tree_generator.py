import pathspec
from pathlib import Path
from teddy_executor.core.ports.outbound.repo_tree_generator import IRepoTreeGenerator


class _TreeFormatter:
    """A private helper class to format a set of paths into a visual tree."""

    def __init__(self, root_dir: Path, included_paths: set[Path]):
        self.root_dir = root_dir
        self.included_paths = included_paths

    def format(self) -> str:
        """Generates a string representation of the file tree."""
        if not self.included_paths:
            return ""

        tree_lines = [f"{self.root_dir.name}/"]
        self._format_recursive(self.root_dir, "", tree_lines)
        return "\n".join(tree_lines)

    def _format_recursive(self, directory: Path, prefix: str, tree_lines: list[str]):
        """Recursively builds the tree string from the set of included paths."""

        children = [p for p in directory.iterdir() if p in self.included_paths]
        children.sort(key=lambda p: (not p.is_dir(), p.name))

        for i, path in enumerate(children):
            connector = "└── " if i == len(children) - 1 else "├── "

            if path.is_dir():
                tree_lines.append(f"{prefix}{connector}{path.name}/")
                new_prefix = prefix + ("    " if i == len(children) - 1 else "│   ")
                self._format_recursive(path, new_prefix, tree_lines)
            else:
                tree_lines.append(f"{prefix}{connector}{path.name}")


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
        all_paths = self.root_dir.rglob("**/*")
        included_paths = set()

        for path in all_paths:
            relative_path_str = str(path.relative_to(self.root_dir))
            # For directories, add a trailing slash to match gitignore behavior
            match_path = relative_path_str + "/" if path.is_dir() else relative_path_str

            if not self.ignore_spec.match_file(match_path):
                # CRITICAL: If a file or directory is not ignored, we must explicitly
                # add it and all of its parent directories to the `included_paths` set.
                # This ensures that if a file like `dist/app/index.html` is un-ignored,
                # the `dist/` and `dist/app/` directories are also present in the
                # final tree, even if they were originally matched by an ignore pattern.
                included_paths.add(path)
                for parent in path.parents:
                    if parent == self.root_dir:
                        break
                    included_paths.add(parent)

        return included_paths

    def generate_tree(self) -> str:
        """
        Generates a string representation of the file tree by gathering paths
        and then delegating to a formatter.
        """
        included_paths = self._get_included_paths()
        formatter = _TreeFormatter(self.root_dir, included_paths)
        return formatter.format()
