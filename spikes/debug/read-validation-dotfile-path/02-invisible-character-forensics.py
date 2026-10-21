"""Locate invisible format characters in recorded artifacts.

Scans text files for codepoints that render as nothing but survive path
normalization, so a link target that displays as an existing file resolves to a
path that does not exist.

Run: uv run python spikes/debug/read-validation-dotfile-path/02-invisible-character-forensics.py
"""

from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

SUSPECT_CODEPOINTS = (0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0x00A0)
SUSPECTS = {chr(code) for code in SUSPECT_CODEPOINTS}
DEFAULT_ROOTS = (".teddy/sessions", "src", "tests", "docs")
TEXT_SUFFIXES = {".md", ".py", ".yaml", ".yml", ".context", ".txt", ".json"}


def scan(root: Path) -> int:
    findings = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            hits = [char for char in line if char in SUSPECTS]
            if not hits:
                continue
            findings += 1
            names = ", ".join(
                f"U+{ord(char):04X} {unicodedata.name(char, 'UNKNOWN')}"
                for char in hits
            )
            print(f"{path}:{number}: {names}")
            print(f"  {line.strip()[:160]!a}")
    return findings


def main(argv: list[str]) -> int:
    roots = [Path(arg) for arg in argv[1:]] or [Path(p) for p in DEFAULT_ROOTS]
    total = 0
    for root in roots:
        if not root.exists():
            print(f"skipped (missing): {root}")
            continue
        print(f"scanning: {root}")
        total += scan(root)
    print(f"\ninvisible-character lines found: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))