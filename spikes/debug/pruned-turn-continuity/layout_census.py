#!/usr/bin/env python3
"""Census prefix breaks over payloads that carry the shipped layout only.

An older payload keeps the per-turn clock rows in its header, so its first
differing byte sits in the header on every pair and hides whatever actually
broke behind it. Counting those pairs would describe a format no user runs, so
a pair is admitted only when BOTH payloads carry the shipped layout: a constant
``# Project Context`` opener plus the closing ``## Runtime`` section that holds
the only per-turn values.

For an admitted pair the census names the section holding the first differing
byte, and when the history section lost a turn it records the status that turn's
own plan and report carried. Validation-failed reports and off-track plans are
removed by different settings, so counting them apart is what turns an anecdote
into a rate. History header suffixes are tallied as well, because a header whose
shape changed between payloads makes a present turn look absent.

Sections and history headers are both located with fence awareness: an embedded
document quotes headings inside its own fenced block.

Read-only: it never writes into a session.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

HEADINGS = (
    "System Information",
    "Session Resources",
    "Session History",
    "Git Status",
    "Project Structure",
    "Resource Contents",
    "Runtime",
)
HISTORY_HEADER = re.compile(r"^### Turn (\d+): (.+)$")
PLAN_STATUS = "- **Status:**"
REPORT_STATUS = "- **Overall Status:**"
PROJECT_CONTEXT = b"# Project Context\n"
RUNTIME_MARKER = b"\n## Runtime\n"
FENCE_CHARS = ("`", "~")


def marks(payload: bytes) -> list[tuple[int, str]]:
    """Byte offsets of the real section headings, skipping fenced content."""
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


def is_shipped_layout(payload: bytes) -> bool:
    """Whether the payload carries the constant header and a runtime tail."""
    return payload.startswith(PROJECT_CONTEXT) and RUNTIME_MARKER in payload


def history_entries(payload: bytes) -> list[tuple[int, str]]:
    """Turn headers rendered outside fences, as (turn id, suffix) pairs."""
    span = spans(payload).get("Session History")
    if not span:
        return []
    body = payload[span[0] : span[1]].decode("utf-8", "replace")
    entries: list[tuple[int, str]] = []
    fence = ""
    for line in body.splitlines():
        stripped = line.strip()
        char = stripped[:1]
        run = len(stripped) - len(stripped.lstrip(char)) if char else 0
        if char and char in FENCE_CHARS and run >= 3:
            if not fence:
                fence = char * run
            elif char == fence[:1] and run >= len(fence) and stripped == char * run:
                fence = ""
            continue
        if fence:
            continue
        match = HISTORY_HEADER.match(line)
        if match:
            entries.append((int(match.group(1)), match.group(2)))
    return entries


def header_value(path: Path, prefix: str) -> str:
    """The value of one header line, or a marker when it is absent."""
    if not path.exists():
        return "no file"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return "absent"


def classify(
    previous: bytes,
    current: bytes,
    plans: dict[int, Path],
    reports: dict[int, Path],
) -> tuple[str, list[int]]:
    """Name the break mechanism and the turns genuinely removed mid-history."""
    shared = shared_prefix_length(previous, current)
    section = section_at(current, shared)
    if section != "Session History":
        return f"{section} changed", []
    before = {turn for turn, _suffix in history_entries(previous)}
    ordered = [turn for turn, _suffix in history_entries(current)]
    after = set(ordered)
    if before and ordered and min(before) != ordered[0]:
        return "front truncation", []
    if not ordered:
        return "history emptied", []
    highest = max(ordered)
    removed = sorted(turn for turn in before - after if turn <= highest)
    if removed:
        return "mid-history removal", removed
    return "history append", []


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions-dir", default=".teddy/sessions")
    parser.add_argument("--show", type=int, default=25, help="sessions to list")
    args = parser.parse_args()

    causes: dict[str, int] = {}
    removed_by_status: dict[str, int] = {}
    header_shapes: dict[str, int] = {}
    admitted = 0
    excluded = 0
    sessions_seen = 0

    for session in sorted(Path(args.sessions_dir).iterdir()):
        if not session.is_dir():
            continue
        turns = sorted(
            (child for child in session.iterdir() if child.is_dir() and child.name.isdigit()),
            key=lambda child: int(child.name),
        )
        payloads = [turn / "input.md" for turn in turns if (turn / "input.md").exists()]
        if len(payloads) < 2:
            continue
        plans = {int(turn.name): turn / "plan.md" for turn in turns}
        reports = {int(turn.name): turn / "report.md" for turn in turns}
        local: dict[str, int] = {}
        local_admitted = 0
        for previous_path, current_path in zip(payloads, payloads[1:]):
            previous = previous_path.read_bytes()
            current = current_path.read_bytes()
            if not (is_shipped_layout(previous) and is_shipped_layout(current)):
                excluded += 1
                continue
            admitted += 1
            local_admitted += 1
            cause, removed = classify(previous, current, plans, reports)
            local[cause] = local.get(cause, 0) + 1
            causes[cause] = causes.get(cause, 0) + 1
            for turn in removed:
                key = (
                    f"{header_value(plans[turn], PLAN_STATUS)}"
                    f" report {header_value(reports[turn], REPORT_STATUS)}"
                )
                removed_by_status[key] = removed_by_status.get(key, 0) + 1
            for _turn, suffix in history_entries(current):
                header_shapes[suffix] = header_shapes.get(suffix, 0) + 1
        if local_admitted:
            sessions_seen += 1
            if sessions_seen <= args.show:
                summary = ", ".join(
                    f"{name} {count}"
                    for name, count in sorted(local.items(), key=lambda kv: -kv[1])
                )
                print(f"  {session.name} [{local_admitted} pairs]: {summary}")

    print("\n== population ==")
    print(f"sessions with shipped-layout pairs {sessions_seen}")
    print(f"admitted pairs {admitted} | excluded pairs {excluded}")

    print("\n== break causes on the shipped layout ==")
    if not admitted:
        print("  none")
    for name, count in sorted(causes.items(), key=lambda item: -item[1]):
        print(f"  {name}: {count} ({count / admitted:.1%} of pairs)")

    print("\n== turns removed mid-history, by their own status ==")
    if removed_by_status:
        for name, count in sorted(removed_by_status.items(), key=lambda item: -item[1]):
            print(f"  {count:>4}  {name}")
    else:
        print("  none")

    print("\n== rendered history header suffixes ==")
    for name, count in sorted(header_shapes.items(), key=lambda item: -item[1]):
        print(f"  {count:>4}  {name}")


if __name__ == "__main__":
    main()
