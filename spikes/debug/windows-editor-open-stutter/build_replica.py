"""Build the sandbox replica of the faulty editor module with the fix applied.

Copies the production module verbatim, then applies the shared basename
normalization to the three classification functions. Each replacement is
asserted so a drift in the source fails loudly instead of producing a stale
replica.
"""

from __future__ import annotations

import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = ROOT / "src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py"
DST = pathlib.Path(__file__).with_name("replica_textual_plan_reviewer_editor.py")

HELPER = '''_WINDOWS_LAUNCHER_SUFFIXES: tuple[str, ...] = (".cmd", ".bat", ".exe")


def _normalize_editor_basename(path: str) -> str:
    """Strip Windows launcher suffixes so extension-less lookups match."""
    base = os.path.basename(path).lower()
    for suffix in _WINDOWS_LAUNCHER_SUFFIXES:
        if base.endswith(suffix):
            return base[: -len(suffix)]
    return base


'''

REPLACEMENTS = [
    (
        "def _run_editor_process(cmd: list[str], **kwargs: Any) -> None:",
        HELPER + "def _run_editor_process(cmd: list[str], **kwargs: Any) -> None:",
    ),
    (
        """    if not editor_cmd:
        return False
    basename = os.path.basename(editor_cmd[0])
    return basename in _CLI_EDITORS""",
        """    if not editor_cmd:
        return False
    return _normalize_editor_basename(editor_cmd[0]) in _CLI_EDITORS""",
    ),
    (
        """    if _is_cli_editor(diff_viewer):
        return True
    if not diff_viewer:
        return False
    basename = os.path.basename(diff_viewer[0]).lower()
    return basename not in ConsoleToolingHelper._DIFF_FLAGS""",
        """    if _is_cli_editor(diff_viewer):
        return True
    if not diff_viewer:
        return False
    return _normalize_editor_basename(diff_viewer[0]) not in ConsoleToolingHelper._DIFF_FLAGS""",
    ),
    (
        """    if not editor_cmd:
        return False
    basename = os.path.basename(editor_cmd[0])
    return basename.lower() in {"vim", "nvim", "vi"}""",
        """    if not editor_cmd:
        return False
    return _normalize_editor_basename(editor_cmd[0]) in {"vim", "nvim", "vi"}""",
    ),
]


def main() -> None:
    text = SRC.read_text(encoding="utf-8")
    for old, new in REPLACEMENTS:
        if old not in text:
            raise SystemExit(f"source drift: expected snippet not found:\n{old}")
        text = text.replace(old, new, 1)
    if "_normalize_editor_basename" not in text:
        raise SystemExit("fix helper not injected")
    DST.write_text(text, encoding="utf-8")
    print(f"wrote {DST} ({len(text)} chars)")


if __name__ == "__main__":
    main()