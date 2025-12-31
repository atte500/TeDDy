import os
import pathspec
from pathlib import Path
from teddy.core.ports.outbound.repo_tree_generator import IRepoTreeGenerator


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
        # Hardcoded patterns to always ignore
        default_ignores = {".git/", ".venv/", "__pycache__/", ".teddy/"}

        lines = list(default_ignores)
        gitignore_path = self.root_dir / ".gitignore"

        if gitignore_path.is_file():
            lines.extend(gitignore_path.read_text().splitlines())

        return pathspec.PathSpec.from_lines("gitwildmatch", lines)

    def generate_tree(self) -> str:
        """
        Generates a string representation of the file tree.
        """
        tree_lines = [f"{self.root_dir.name}/"]

        for root, dirs, files in os.walk(self.root_dir, topdown=True):
            rel_root = Path(root).relative_to(self.root_dir)
            rel_root_str = str(rel_root) if str(rel_root) != "." else ""

            # Filter directories in-place using the RCA-verified method
            dirs[:] = [
                d
                for d in sorted(dirs)
                if not self.ignore_spec.match_file(
                    os.path.join(rel_root_str, d) + os.sep
                )
            ]
            files = sorted(
                [
                    f
                    for f in files
                    if not self.ignore_spec.match_file(os.path.join(rel_root_str, f))
                ]
            )

            # Draw the tree structure
            level = len(rel_root.parts)
            indent = "│   " * level

            # Combine and sort dirs and files for correct connector logic
            items = [d + "/" for d in dirs] + files

            for i, name in enumerate(items):
                connector = "└── " if i == len(items) - 1 else "├── "
                tree_lines.append(f"{indent}{connector}{name}")

        return "\n".join(tree_lines)
