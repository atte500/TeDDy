#!/usr/bin/env python3
"""Dump each turn's status and the blocks a pruned turn leaves behind.

Failure pruning keys off a plan's ``- **Status:**`` line. What a later turn
still inherits after a plan and its report are deselected is the rationale
summary plus the Notes list, so printing both per turn makes the continuity
readable instead of assumed: a finding that reappears in its successor survived
the prune, and one that does not was lost with the turn. The pruned turn's own
plan.md keeps existing on disk; only its place in the payload is gone, which is
why this can compare the two.

Read-only: it never writes into a session.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

STATUS = re.compile(r"^- \*\*Status:\*\*(.*)$", re.MULTILINE)
NOTE = re.compile(r"^- \[[^\]]+\].*$", re.MULTILINE)


def block(text: str, heading: str) -> str:
    """The body between one level-three heading and the next one."""
    marker = f"### {heading}"
    start = text.find(marker)
    if start < 0:
        return ""
    start += len(marker)
    end = text.find("\n### ", start)
    return text[start : end if end >= 0 else len(text)].strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True, help="path to a session dir")
    parser.add_argument("--first", type=int, default=1)
    parser.add_argument("--last", type=int, default=99)
    parser.add_argument("--width", type=int, default=900)
    args = parser.parse_args()

    session = Path(args.session)
    turns = sorted(
        (child for child in session.iterdir() if child.is_dir() and child.name.isdigit()),
        key=lambda child: int(child.name),
    )
    for turn in turns:
        number = int(turn.name)
        if not (args.first <= number <= args.last):
            continue
        plan_path = turn / "plan.md"
        if not plan_path.exists():
            print(f"\n===== turn {number:02d}: no plan.md")
            continue
        plan = plan_path.read_text(encoding="utf-8")
        status = STATUS.search(plan)
        state = status.group(1).strip() if status else "(no status line)"
        summary = block(plan, "Summary")
        notes = block(plan, "Notes")
        print(f"\n===== turn {number:02d} status {state}")
        print(f"--- summary ({len(summary)} B)")
        print(summary[: args.width])
        print(f"--- notes ({len(notes)} B)")
        for line in NOTE.findall(notes):
            print(f"  {line}")


if __name__ == "__main__":
    main()
