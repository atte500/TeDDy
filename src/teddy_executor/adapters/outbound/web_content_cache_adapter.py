"""Filesystem implementation of the session content cache port."""

import json
from pathlib import Path
from typing import Mapping, Optional

from teddy_executor.core.domain.models.exceptions import WebContentCacheError


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
        """Layer the supplied bodies over the stored map, keeping siblings."""
        if session_root is None:
            return
        directory = Path(session_root)
        merged = self.load_entries(session_root)
        merged.update(entries)
        cache_path = directory / self.CACHE_FILENAME
        try:
            directory.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps(merged, ensure_ascii=False), encoding="utf-8", newline=""
            )
        except OSError as exc:
            raise WebContentCacheError(
                f"cannot persist the session content cache: {exc}",
                session_root=session_root,
            ) from exc
