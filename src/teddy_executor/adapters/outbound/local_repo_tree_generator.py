import logging
import os
from pathlib import Path
from teddy_executor.core.ports.outbound.repo_tree_generator import IRepoTreeGenerator

logger = logging.getLogger(__name__)


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

    def generate_tree(self) -> str:
        """
        Generates a string representation of the file tree in a single pass.
        """
        sections: list[tuple[str, str, list[str]]] = []
        root_names = self._collect_directory(self.root_dir, "", sections)
        # Sections sort by their relative path, and the root resolves to ".",
        # so a top-level name below "." (for example "!important") renders
        # before the root block. The "." key preserves that exact order.
        sections.append((".", "", root_names))
        sections.sort(key=lambda item: item[0])

        rendered: list[str] = []
        for _sort_key, relative_path, names in sections:
            if not names:
                continue
            if relative_path:
                rendered.append("\n".join([f"./{relative_path}:"] + names))
            else:
                rendered.append("\n".join(names))
        return "\n\n".join(rendered)

    def _collect_directory(
        self,
        directory: str | Path,
        relative_path: str,
        sections: list[tuple[str, str, list[str]]],
    ) -> list[str]:
        """
        Collects one directory's visible names and recurses into its children.

        Directory and symlink flags come from the scan cache, so each entry
        costs no additional stat call. Symlinks are listed as files and are
        never followed, which keeps circular links from recursing.
        """
        names: list[str] = []
        try:
            with os.scandir(directory) as iterator:
                entries = list(iterator)
        except PermissionError:
            logger.debug("Skipping unreadable directory %s", directory, exc_info=True)
            return names

        for entry in entries:
            is_directory = entry.is_dir(follow_symlinks=False)
            child_path = (
                f"{relative_path}/{entry.name}" if relative_path else entry.name
            )
            match_path = (child_path + "/") if is_directory else child_path
            if self.ignore_spec.match_file(match_path):
                continue
            names.append(entry.name)
            if is_directory:
                child_names = self._collect_directory(entry.path, child_path, sections)
                sort_key = child_path.replace("/", os.sep).lower()
                sections.append((sort_key, child_path, child_names))

        names.sort(key=str.lower)
        return names
