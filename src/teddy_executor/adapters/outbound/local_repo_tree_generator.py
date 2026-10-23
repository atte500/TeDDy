import logging
import os
from pathlib import Path
from teddy_executor.core.domain.models.config_schema import DEFAULT_APP_CONFIG
from teddy_executor.core.ports.outbound.repo_tree_generator import IRepoTreeGenerator

logger = logging.getLogger(__name__)

UNREADABLE_MARKER = "[unreadable]"


class LocalRepoTreeGenerator(IRepoTreeGenerator):
    """
    An adapter that generates a file tree for the local repository,
    respecting .gitignore and .teddyignore rules.
    """

    def __init__(
        self,
        root_dir: str = ".",
        max_depth: int = DEFAULT_APP_CONFIG.context.max_depth,
        max_children: int = DEFAULT_APP_CONFIG.context.max_children,
    ):
        from teddy_executor.adapters.outbound.filesystem_helpers import (
            load_ignore_spec,
        )

        assert max_depth >= 0, f"max_depth must be non-negative, got {max_depth}"
        assert max_children >= 1, f"max_children must be positive, got {max_children}"
        self.root_dir = Path(root_dir).resolve()
        self.ignore_spec = load_ignore_spec(self.root_dir)
        self._max_depth = max_depth
        self._max_children = max_children

    @property
    def max_depth(self) -> int:
        """The configured maximum directory nesting depth."""
        return self._max_depth

    @property
    def max_children(self) -> int:
        """The configured maximum visible entries per non-root directory."""
        return self._max_children

    def generate_tree(self) -> str:
        """
        Generates a string representation of the file tree in a single pass.
        """
        sections: list[tuple[str, str, list[str]]] = []
        root_names = self._collect_directory(self.root_dir, "", sections, is_root=True)
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
        is_root: bool = False,
    ) -> list[str]:
        """
        Collects one directory's visible names and recurses into its children.

        One scan supplies both limits. A directory at or beyond the configured
        depth limit renders one compact count notice instead of expanding, so
        truncation is never silent. A non-root directory holding more visible
        entries than the width cap renders the same notice and withholds its
        descendants, because names without their parent folder cannot be
        mapped. The project root is exempt from the width cap, because it is
        the only place where a top-level file is named. An unreadable directory
        renders an explicit marker rather than an empty section, so it never
        looks like a readable empty directory. Directory and symlink flags come
        from the scan cache, so each entry costs no additional stat call.
        Symlinks are listed as files and are never followed, which keeps
        circular links from recursing.
        """
        if depth >= self._max_depth:
            return self._omission_notice(directory, relative_path)

        entries = self._scan_visible_entries(directory, relative_path)
        if entries is None:
            return [UNREADABLE_MARKER]

        if not is_root and len(entries) > self._max_children:
            return [self._compact_notice(entries)]

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

    def _omission_notice(self, directory: str | Path, relative_path: str) -> list[str]:
        """
        Renders the compact notice for a directory at the depth limit.

        Counts only the visible immediate children after ignore rules. An
        unreadable directory renders the unreadable marker instead, and a
        directory with no visible child renders nothing, so a genuinely empty
        directory is not shown as an omission.
        """
        entries = self._scan_visible_entries(directory, relative_path)
        if entries is None:
            return [UNREADABLE_MARKER]
        if not entries:
            return []
        return [self._compact_notice(entries)]

    @staticmethod
    def _compact_notice(entries: list[tuple[os.DirEntry, bool, str]]) -> str:
        """Render the compact ``[X folders, Y files]`` notice for ``entries``."""
        folders = sum(1 for _entry, is_directory, _path in entries if is_directory)
        files = len(entries) - folders
        folder_noun = "folder" if folders == 1 else "folders"
        file_noun = "file" if files == 1 else "files"
        return f"[{folders} {folder_noun}, {files} {file_noun}]"
