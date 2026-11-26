#!/usr/bin/env python3
"""Census the mechanisms that end a shared payload prefix across all sessions.

One session showed three kinds of history break, so only a corpus tells them
apart. Per consecutive payload pair this names the section holding the first
differing byte, and for a turn that vanished from the middle of the history it
records the status its own plan and report carried. A validation-failed report
and an off-track plan are pruned by different settings, so counting them apart
is what turns an anecdote into a rate.

Sections are located with fence awareness: an embedded document quotes section
headings inside its own fenced block, so a heading only marks a section when it
sits outside a fence.

Read-only: it never writes into a session.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

HEADINGS = (
    "Session Resources",
    "Session History",
    "Git Status",
    "Project Structure",
    "Resource Contents",
    "Runtime",
)
HISTORY_HEADER = re.compile(r"^### Turn (\d+): (?:Plan|Report)$")
PLAN_STATUS = "- **Status:**"
REPORT_STATUS = "- **Overall Status:**"


def marks(payload: bytes) -> list[tuple[int, str]]:
    """Byte offsets of the real section headings, in document order."""
    found: list[tuple[int, str]] = []
    fence = b""
    offset = 0
    for line in payload.splitlines(keepends=True):
        stripped = line.strip()
        char = stripped[:1]
        run = len(stripped) - len(stripped.lstrip(char)) if char else 0
        if char in (b"`", b"~") and run >= 3:
            if not fence:
                fence = char * run
            elif char == fence[:1] and run >= len(fence) and stripped == char * run:
                fence = b""
        elif not fence:
            for name in HEADINGS:
                if line.rstrip(b"\r\n") == f"## {name}".encode():
                    found.append((offset, name))
        offset += len(line)
    return found


def spans(payload: bytes) -> dict[str, tuple[int, int]]:
    """Each present section's byte span, bounded by the next real heading."""
    located = marks(payload)
    return {
        name: (offset, located[index + 1][0] if index + 1 < len(located) else len(payload))
        for index, (offset, name) in enumerate(located)
    }


def shared_prefix_length(left: bytes, right: bytes) -> int:
    """Binary-search the first differing byte between two payloads."""
    low, high = 0, min(len(left), len(right))
    while low < high:
        middle = (low + high + 1) // 2
        if left[:middle] == right[:middle]:
            low = middle
        else:
            high = middle - 1
    return low


def section_at(payload: bytes, offset: int) -> str:
    """Name the section holding the offset, or header before the first one."""
    name = "header"
    for section, (start, _end) in sorted(
        spans(payload).items(), key=lambda item: item[1][0]
    ):
        if start > offset:
            break
        name = section
    return name


def history_ids(payload: bytes) -> list[int]:
    """The turn numbers whose plan or report the payload renders."""
    span = spans(payload).get("Session History")
    if not span:
        return []
    body = payload[span[0] : span[1]].decode("utf-8", "replace")
    found = {
        int(match.group(1))
        for match in (HISTORY_HEADER.match(line) for line in body.splitlines())
        if match
    }
    return sorted(found)


def header_value(path: Path, prefix: str) -> str:
    """The value of one header line, or a marker when it is absent."""
    if not path.exists():
        return "(no file)"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return "(absent)"


def classify(
    previous: bytes,
    current: bytes,
    plans: dict[int, Path],
    reports: dict[int, Path],
) -> tuple[str, list[str]]:
    """Name the break mechanism and describe every turn removed mid-history."""
    shared = shared_prefix_length(previous, current)
    section = section_at(current, shared)
    if section != "Session History":
        return f"{section} changed", []
    before = history_ids(previous)
    after = history_ids(current)
    if before and after and before[0] != after[0]:
        return "retention front truncation", []
    removed = [turn for turn in before if turn not in after and after and turn <= after[-1]]
    if removed:
        detail = [
            f"{turn:02d} plan {header_value(plans[turn], PLAN_STATUS)}"
            f" report {header_value(reports[turn], REPORT_STATUS)}"
            for turn in removed
            if turn in plans and turn in reports
        ]
        return "mid-history removal", detail
    return "history append", []


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions-dir", default=".teddy/sessions")
    parser.add_argument("--min-payloads", type=int, default=3)
    parser.add_argument("--show", type=int, default=40, help="sessions to list")
    args = parser.parse_args()

    causes: dict[str, int] = {}
    removed_by_status: dict[str, int] = {}
    pairs = 0
    sessions = 0

    for session in sorted(Path(args.sessions_dir).iterdir()):
        if not session.is_dir():
            continue
        turns = sorted(
            (child for child in session.iterdir() if child.is_dir() and child.name.isdigit()),
            key=lambda child: int(child.name),
        )
        payloads = [turn / "input.md" for turn in turns if (turn / "input.md").exists()]
        if len(payloads) < args.min_payloads:
            continue
        sessions += 1
        plans = {int(turn.name): turn / "plan.md" for turn in turns}
        reports = {int(turn.name): turn / "report.md" for turn in turns}
        local: dict[str, int] = {}
        for previous_path, current_path in zip(payloads, payloads[1:]):
            cause, detail = classify(
                previous_path.read_bytes(),
                current_path.read_bytes(),
                plans,
                reports,
            )
            pairs += 1
            local[cause] = local.get(cause, 0) + 1
            causes[cause] = causes.get(cause, 0) + 1
            for line in detail:
                key = line.split(" plan ", 1)[1]
                removed_by_status[key] = removed_by_status.get(key, 0) + 1
        summary = ", ".join(
            f"{name} {count}" for name, count in sorted(local.items(), key=lambda kv: -kv[1])
        )
        if sessions <= args.show:
            print(f"  {session.name} [{len(payloads)} payloads]: {summary}")

    print("\n== corpus ==")
    print(f"sessions {sessions} | pairs {pairs}")
    for name, count in sorted(causes.items(), key=lambda item: -item[1]):
        share = count / pairs if pairs else 0.0
        print(f"  {name}: {count} ({share:.1%} of pairs)")

    print("\n== turns removed from the middle, by their own status ==")
    if removed_by_status:
        for name, count in sorted(removed_by_status.items(), key=lambda item: -item[1]):
            print(f"  {count:>4}  {name}")
    else:
        print("  none")


if __name__ == "__main__":
    main()
