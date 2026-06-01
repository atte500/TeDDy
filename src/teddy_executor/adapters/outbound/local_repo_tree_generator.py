import os
from pathlib import Path
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
        from teddy_executor.adapters.outbound.filesystem_helpers import (
            load_ignore_spec,
        )

        self.root_dir = Path(root_dir).resolve()
        self.ignore_spec = load_ignore_spec(self.root_dir)

    def _get_included_paths(self) -> set[Path]:
        """
        Walks the directory and returns a set of all files and parent directories
        that are not excluded by the ignore spec.
        """
        from teddy_executor.adapters.outbound.filesystem_helpers import walk_recursive

        included_paths: set[Path] = set()
        for entry, _ in walk_recursive(self.root_dir, self.root_dir, self.ignore_spec):
            # If not ignored, add to set
            included_paths.add(entry)

            # Ensure parent connectivity
            for parent in entry.parents:
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
        formatter = _RecursiveListFormatter(self.root_dir, included_paths)
        return formatter.format()
