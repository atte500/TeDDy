#!/usr/bin/env python3
"""Separate a turn that was pruned from one that was never carried forward.

``turn.context`` is the persisted list of paths a turn inherited, so a turn id
listed there but absent from the rendered history was deselected while the
payload was assembled, while an id absent from both was never carried at all.
Reading the two side by side names the mechanism instead of guessing it, and the
distinction matters: a pruning defect and a carry-over defect need different
fixes, and only the first one is a matter of policy.

Per turn this prints the carried ids, the rendered ids, the ids that dropped
between them, and each dropped turn's plan status and report status. It also
estimates the carried turn-scope token load, because a budget prune removes the
same shape from the payload as a status prune and the two are indistinguishable
without that number. The estimate is characters over four, so it is an order of
magnitude, never a measurement.

Rendered headers are read outside fences only, so a quoted document cannot
invent a turn here.

Read-only: it never writes into a session.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

TURN_PATH = re.compile(r"/(\d{1,3})/(?:input|plan|report)\.md$")
HISTORY_LINE = re.compile(r"^### Turn (\d+): (Plan|Report)$")
PLAN_STATUS = "- **Status:**"
REPORT_STATUS = "- **Overall Status:**"
USER_REQUEST = "## User Request"
PRUNED_MARKER = "pruned_context"
CHARS_PER_TOKEN = 4


def outside_fence_lines(payload: bytes) -> list[str]:
    """Every payload line that sits outside a fenced block."""
    kept: list[str] = []
    fence = b""
    for line in payload.splitlines():
        stripped = line.strip()
        char = stripped[:1]
        run = len(stripped) - len(stripped.lstrip(char)) if char else 0
        if char in (b"`", b"~") and run >= 3:
            if not fence:
                fence = char * run
            elif char == fence[:1] and run >= len(fence) and stripped == char * run:
                fence = b""
            continue
        if not fence:
            kept.append(line.decode("utf-8", "replace"))
    return kept


def rendered_ids(payload_path: Path) -> list[int]:
    """The turn ids whose plan or report the payload renders."""
    if not payload_path.exists():
        return []
    found: set[int] = set()
    for line in outside_fence_lines(payload_path.read_bytes()):
        match = HISTORY_LINE.match(line)
        if match:
            found.add(int(match.group(1)))
    return sorted(found)


def carried_ids(turn_dir: Path) -> list[int]:
    """The turn ids listed in the turn's inherited context manifest."""
    manifest = turn_dir / "turn.context"
    if not manifest.exists():
        return []
    found: set[int] = set()
    for line in manifest.read_text(encoding="utf-8").splitlines():
        match = TURN_PATH.search(line.strip())
        if match:
            found.add(int(match.group(1)))
    return sorted(found)


def line_value(path: Path, prefix: str) -> str:
    """The value of one header line, or a marker when it is absent."""
    if not path.exists():
        return "(no file)"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return "(absent)"


def carried_bytes(turn_dir: Path) -> int:
    """Total size of the files the turn inherited, for a token estimate."""
    manifest = turn_dir / "turn.context"
    if not manifest.exists():
        return 0
    total = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        candidate = Path(line.strip())
        if candidate.is_file():
            total += candidate.stat().st_size
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True, help="path to a session dir")
    parser.add_argument("--budget", type=int, default=50000, help="token budget")
    parser.add_argument("--width", type=int, default=12, help="characters to align")
    args = parser.parse_args()

    session = Path(args.session)
    turns = sorted(
        (child for child in session.iterdir() if child.is_dir() and child.name.isdigit()),
        key=lambda child: int(child.name),
    )
    plans = {int(turn.name): turn / "plan.md" for turn in turns}
    reports = {int(turn.name): turn / "report.md" for turn in turns}
    over_budget: list[str] = []
    pruned: dict[str, int] = {}
    uncarried: dict[str, int] = {}

    for turn in turns:
        number = int(turn.name)
        carried = carried_ids(turn)
        rendered = rendered_ids(turn / "input.md")
        estimate = carried_bytes(turn) // CHARS_PER_TOKEN
        status = line_value(plans[number], PLAN_STATUS)
        report = line_value(reports[number], REPORT_STATUS)
        flag = "over" if estimate > args.budget else "under"
        print(
            f"turn {number:02d} | carried {carried} | rendered {rendered}"
            f" | est {estimate:>7,} tok ({flag})"
            f" | plan {status} | report {report}"
        )
        if estimate > args.budget:
            over_budget.append(f"{number:02d}")
        if not rendered:
            continue
        highest = rendered[-1]
        for value in range(1, highest + 1):
            if value in rendered:
                continue
            if value in carried:
                pruned[status if value == number else plans.get(value, Path()).name] = (
                    pruned.get(status if value == number else plans.get(value, Path()).name, 0)
                ) + 1
            else:
                uncarried["absent from manifest"] = (
                    uncarried.get("absent from manifest", 0) + 1
                )

    print("\n== verdict ==")
    dropped_pruned = sum(pruned.values())
    dropped_uncarried = sum(uncarried.values())
    print(f"dropped but carried: {dropped_pruned}")
    print(f"dropped and never carried: {dropped_uncarried}")
    print(f"turns whose carried load exceeds {args.budget:,} tok: {over_budget or 'none'}")

    print("\n== dropped turns in detail ==")
    for turn in turns:
        number = int(turn.name)
        rendered = rendered_ids(turn / "input.md")
        if not rendered:
            continue
        for value in range(1, rendered[-1] + 1):
            if value in rendered:
                continue
            report_path = reports.get(value)
            print(
                f"  turn {value:02d} dropped by turn {number:02d}"
                f" | plan {line_value(plans.get(value, Path()), PLAN_STATUS)}"
                f" | report {line_value(report_path or Path(), REPORT_STATUS)}"
                f" | user request {line_value(report_path or Path(), USER_REQUEST)}"
                f" | pruned marker {line_value(plans.get(value, Path()), '- **')}"
            )


if __name__ == "__main__":
    main()
