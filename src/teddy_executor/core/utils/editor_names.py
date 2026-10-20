"""Shared editor-command normalization for classification lookups."""

from __future__ import annotations

import os

_LAUNCHER_SUFFIXES: tuple[str, ...] = (".cmd", ".bat", ".exe")


def normalize_editor_basename(editor_path: str | None) -> str:
    """Return the lowercased basename with any Windows launcher suffix removed.

    Windows resolves editor names through ``shutil.which``, which returns a
    launcher wrapper such as ``codium.CMD``. The classification tables are keyed
    on the bare name, so callers must normalize before a lookup. The suffix match
    is case-insensitive because Windows filesystems are, and the remaining name
    is lowercased so table lookups stay stable.
    """
    if not editor_path:
        return ""
    basename = os.path.basename(editor_path).lower()
    for suffix in _LAUNCHER_SUFFIXES:
        if basename.endswith(suffix):
            return basename[: -len(suffix)]
    return basename
