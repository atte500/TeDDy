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


# Terminal editors that require a suspend/resume handover instead of the
# non-blocking GUI launch. The set is the single source of truth, so the TUI
# reviewer and the console ask loop classify editors identically.
CLI_EDITORS: frozenset[str] = frozenset(
    {
        "vim",
        "nvim",
        "vi",
        "nano",
        "micro",
        "emacs",
        "pico",
        "helix",
        "hx",
        "kak",
    }
)


def is_cli_editor(editor_cmd: list[str] | None) -> bool:
    """Return True when the resolved editor command is a terminal (CLI) editor.

    The command list carries the resolved launcher path as its first element, so
    the basename is normalized first. Unknown editors, empty commands, and
    ``None`` classify as False and default to the non-blocking GUI launch.
    """
    if not editor_cmd:
        return False
    return normalize_editor_basename(editor_cmd[0]) in CLI_EDITORS
