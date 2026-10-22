import logging
import os
from pathlib import Path
from teddy_executor.core.domain.models.config_schema import DEFAULT_APP_CONFIG
from teddy_executor.core.ports.outbound.repo_tree_generator import IRepoTreeGenerator

logger = logging.getLogger(__name__)

UNREADABLE_MARKER = "[... directory not expanded (unreadable): 0 folders, 0 files]"


class LocalRepoTreeGenerator(IRepoTreeGenerator):
    """
    An adapter that generates a file tree for the local repository,
    respecting .gitignore and .teddyignore rules.
    """

    def __init__(
        self,
        root_dir: str = ".",
        max_depth: int = DEFAULT_APP_CONFIG.context.max_tree_depth,
        max_tree_width: int = DEFAULT_APP_CONFIG.context.max_tree_width,
    ):
        from teddy_executor.adapters.outbound.filesystem_helpers import (
            load_ignore_spec,
        )

        assert max_depth >= 0, f"max_depth must be non-negative, got {max_depth}"
        assert max_tree_width >= 1, (
            f"max_tree_width must be positive, got {max_tree_width}"
        )
        self.root_dir = Path(root_dir).resolve()
        self.ignore_spec = load_ignore_spec(self.root_dir)
        self._max_depth = max_depth
        self._max_tree_width = max_tree_width

    @property
    def max_depth(self) -> int:
        """The configured maximum directory nesting depth."""
        return self._max_depth

    @property
    def max_tree_width(self) -> int:
        """The configured maximum visible entries per non-root directory."""
        return self._max_tree_width

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
        depth: int = 0,
    ) -> list[str]:
        """
        Collects one directory's visible names and recurses into its children.

        A directory at or beyond the configured depth limit renders one
        omission marker instead of expanding, so truncation is never silent.
        An unreadable directory renders an explicit marker rather than an
        empty section, so it never looks like a readable empty directory.
        Directory and symlink flags come from the scan cache, so each entry
        costs no additional stat call. Symlinks are listed as files and are
        never followed, which keeps circular links from recursing.
        """
        if depth >= self._max_depth:
            marker = self._depth_limit_marker(directory, relative_path)
            return [marker] if marker else []

        entries = self._scan_visible_entries(directory, relative_path)
        if entries is None:
            return [UNREADABLE_MARKER]

        names: list[str] = []
        for entry, is_directory, child_path in entries:
            names.append(entry.name)
            if is_directory:
                child_names = self._collect_directory(
                    entry.path, child_path, sections, depth + 1
                )
                sort_key = child_path.replace("/", os.sep).lower()
                sections.append((sort_key, child_path, child_names))

        names.sort(key=str.lower)
        return names

    def _scan_visible_entries(
        self, directory: str | Path, relative_path: str
    ) -> list[tuple[os.DirEntry, bool, str]] | None:
        """
        Returns one visible immediate child per entry after ignore rules.

        The scan is materialized before its context closes, so each DirEntry
        still answers its cached directory flag. An unreadable directory
        returns ``None`` so callers can tell it apart from a readable empty
        one, which returns an empty list.
        """
        try:
            with os.scandir(directory) as iterator:
                entries = list(iterator)
        except PermissionError:
            logger.debug("Skipped unreadable directory %s", directory, exc_info=True)
            return None
        visible: list[tuple[os.DirEntry, bool, str]] = []
        for entry in entries:
            is_directory = entry.is_dir(follow_symlinks=False)
            child_path = (
                f"{relative_path}/{entry.name}" if relative_path else entry.name
            )
            match_path = (child_path + "/") if is_directory else child_path
            if self.ignore_spec.match_file(match_path):
                continue
            visible.append((entry, is_directory, child_path))
        return visible

    def _depth_limit_marker(self, directory: str | Path, relative_path: str) -> str:
        """
        Renders the omission marker for a directory at the depth limit.

        Counts only the visible immediate children after ignore rules. An
        unreadable directory renders the unreadable marker instead. Returns an
        empty string when no child is visible, so a genuinely empty directory
        renders no section rather than a misleading marker.
        """
        entries = self._scan_visible_entries(directory, relative_path)
        if entries is None:
            return UNREADABLE_MARKER
        folders = sum(1 for _entry, is_directory, _path in entries if is_directory)
        files = len(entries) - folders
        if not folders and not files:
            return ""
        folder_noun = "folder" if folders == 1 else "folders"
        file_noun = "file" if files == 1 else "files"
        return (
            f"[... directory not expanded (depth limit {self._max_depth}): "
            f"{folders} {folder_noun}, {files} {file_noun}]"
        )
