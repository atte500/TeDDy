"""Sandbox replica of the repository tree generator with a fused traversal.

The production adapter walks the repository into a set of included paths and
then formats that set with a second filesystem pass. Probe 09 proved that a
single pass which threads relative path strings and reads the directory flag
from the scan cache reproduces the production output byte for byte. This
replica keeps the same constructor, resolved root, and ignore spec, so the
verification script can substitute it without touching production code.
"""

import logging
import os
from pathlib import Path
from typing import List, Tuple

from teddy_executor.adapters.outbound.filesystem_helpers import load_ignore_spec
from teddy_executor.core.ports.outbound.repo_tree_generator import IRepoTreeGenerator

logger = logging.getLogger(__name__)


class LocalRepoTreeGenerator(IRepoTreeGenerator):
    """Generates a repository tree while reading each directory exactly once."""

    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir).resolve()
        self.ignore_spec = load_ignore_spec(self.root_dir)

    def generate_tree(self) -> str:
        """Render the recursive listing from a single traversal."""
        sections: List[Tuple[str, str, List[str]]] = []
        root_names = self._collect_directory(self.root_dir, "", sections)
        # The production formatter sorts every section by its relative path,
        # and the root resolves to ".". Keeping the same key preserves the
        # exact section order, including directories that sort before ".".
        sections.append((".", "", root_names))
        sections.sort(key=lambda item: item[0])

        rendered: List[str] = []
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
        sections: List[Tuple[str, str, List[str]]],
    ) -> List[str]:
        """Collect one directory's visible names and recurse into its children."""
        names: List[str] = []
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