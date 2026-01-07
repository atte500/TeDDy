import pathspec
from pathlib import Path
from teddy_executor.core.ports.outbound.repo_tree_generator import IRepoTreeGenerator


class LocalRepoTreeGenerator(IRepoTreeGenerator):
    """
    An adapter that generates a file tree for the local repository,
    respecting .gitignore rules, based on a verified RCA.
    """

    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir).resolve()
        self.ignore_spec = self._load_ignore_spec()

    def _load_ignore_spec(self) -> pathspec.PathSpec:
        """Loads .gitignore and combines it with default ignores."""
        default_ignores = {".git/", ".venv/", "__pycache__/", ".teddy/", ".ruff_cache/"}

        lines = list(default_ignores)
        gitignore_path = self.root_dir / ".gitignore"

        if gitignore_path.is_file():
            # Add gitignore patterns for pathspec, including the file itself
            lines.append(gitignore_path.name)
            lines.extend(gitignore_path.read_text().splitlines())

        return pathspec.PathSpec.from_lines("gitwildmatch", lines)

    def generate_tree(self) -> str:
        """
        Generates a string representation of the file tree.
        """
        tree_lines = [f"{self.root_dir.name}/"]
        self._generate_tree_recursive(self.root_dir, "", tree_lines)
        return "\n".join(tree_lines)

    def _generate_tree_recursive(
        self, directory: Path, prefix: str, tree_lines: list[str]
    ):
        """Recursively builds the tree string."""

        # Get all children and filter them using pathspec
        children = list(directory.iterdir())

        # IMPORTANT: pathspec needs paths relative to the root where .gitignore is
        filtered_children = [
            p
            for p in children
            if not self.ignore_spec.match_file(
                # Add trailing slash for directories to match patterns like `dist/`
                str(p.relative_to(self.root_dir)) + ("/" if p.is_dir() else "")
            )
        ]

        # Sort by type (directories first), then by name
        filtered_children.sort(key=lambda p: (not p.is_dir(), p.name))

        for i, path in enumerate(filtered_children):
            connector = "└── " if i == len(filtered_children) - 1 else "├── "

            if path.is_dir():
                tree_lines.append(f"{prefix}{connector}{path.name}/")
                new_prefix = prefix + (
                    "    " if i == len(filtered_children) - 1 else "│   "
                )
                self._generate_tree_recursive(path, new_prefix, tree_lines)
            else:
                tree_lines.append(f"{prefix}{connector}{path.name}")
