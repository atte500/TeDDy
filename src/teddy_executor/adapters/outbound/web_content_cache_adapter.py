"""Filesystem implementation of the session content cache port."""

import json
import logging
import threading
from pathlib import Path
from typing import Mapping, Optional

from teddy_executor.core.domain.models.exceptions import WebContentCacheError

logger = logging.getLogger(__name__)

# One process-wide lock shared across adapter instances, because the adapter is
# registered transient: concurrent merges into one session root must serialize
# their read-modify-write window instead of dropping each other's entry.
_MERGE_LOCK = threading.Lock()

_TEMP_SUFFIX = ".tmp"


class WebContentCacheAdapter:
    """Stores fetched remote bodies in ``.web_cache.json`` under a session root.

    The cache filename and the flat URL-to-body JSON shape live here alone, so no
    core component knows how the session cache is persisted.
    """

    CACHE_FILENAME = ".web_cache.json"

    def load_entries(self, session_root: Optional[str]) -> dict[str, str]:
        """Read the session's URL-keyed bodies, degrading to empty on damage."""
        if session_root is None:
            return {}
        cache_path = Path(session_root) / self.CACHE_FILENAME
        if not cache_path.exists():
            return {}
        try:
            parsed = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {}
        if not isinstance(parsed, dict):
            return {}
        entries: dict[str, str] = {}
        for key, value in parsed.items():
            if not isinstance(key, str) or not isinstance(value, str):
                return {}
            entries[key] = value
        return entries

    def merge_entries(
        self, session_root: Optional[str], entries: Mapping[str, str]
    ) -> None:
        """Layer the supplied bodies over the stored map, keeping siblings.

        The read-modify-write runs as one critical section under a lock shared by
        every instance, and the result replaces the cache file atomically, so a
        concurrent fetch can neither drop a sibling entry nor observe a partial
        document.
        """
        if session_root is None:
            return
        directory = Path(session_root)
        cache_path = directory / self.CACHE_FILENAME
        temp_path = cache_path.with_name(cache_path.name + _TEMP_SUFFIX)
        with _MERGE_LOCK:
            merged = self.load_entries(session_root)
            merged.update(entries)
            try:
                directory.mkdir(parents=True, exist_ok=True)
                temp_path.write_text(
                    json.dumps(merged, ensure_ascii=False),
                    encoding="utf-8",
                    newline="",
                )
                temp_path.replace(cache_path)
            except OSError as exc:
                self._discard_temp_file(temp_path)
                raise WebContentCacheError(
                    f"cannot persist the session content cache: {exc}",
                    session_root=session_root,
                ) from exc

    def _discard_temp_file(self, temp_path: Path) -> None:
        """Remove a partial write, reporting a failure instead of hiding it."""
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            logger.warning(
                "Could not remove the partial cache temp file %s.",
                temp_path,
                exc_info=True,
            )
