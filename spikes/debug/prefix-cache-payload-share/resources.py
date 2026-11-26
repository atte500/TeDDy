#!/usr/bin/env python3
"""Attribute Session Resources prefix breaks to the document that changed.

Sections are bounded by the KNOWN section headings only. A span must never end
at the next ``## `` line: the resource documents and the plan bodies carry their
own ``## `` headings inside their fenced content, so any looser bound truncates a
section at the first Markdown heading it contains.

For each consecutive payload pair this names the session-resource document whose
content differs, the byte offset where the match ended, the share that offset
represents, and the share that would survive if that document had stayed byte
identical. History breaks are reported separately as front truncation (retention)
or mid-section removal (budget or failure pruning).

Read-only: it never writes into a session.
"""

from __future__ import annotations

import argparse
import re
import statistics
from pathlib import Path

KNOWN_SECTIONS = (
    "Session Resources",
    "Session History",
    "Git Status",
    "Project Structure",
    "Resource Contents",
    "Runtime",
)
MEMBER = re.compile(rb"\n### \[([^\]]+)\]\([^)]*\)")
HISTORY_MEMBER = re.compile(rb"\n### ((?:Turn \d+: (?:Plan|Report))|Initial Request)")


def spans(payload: bytes) -> dict[str, tuple[int, int]]:
    """Each known section's byte span, bounded only by the next known heading."""
    marks: list[tuple[int, str]] = []
    for name in KNOWN_SECTIONS:
        offset = payload.find(f"\n## {name}\n".encode())
        if offset >= 0:
            marks.append((offset, name))
    marks.sort()
    return {
        name: (offset, marks[index + 1][0] if index + 1 < len(marks) else len(payload))
        for index, (offset, name) in enumerate(marks)
    }


def section_at(payload: bytes, offset: int) -> str:
    """Name the section holding ``offset`` (``header`` before the first one)."""
    name = "header"
    for section, (start, _end) in sorted(spans(payload).items(), key=lambda t: t[1][0]):
        if start > offset:
            break
        name = section
    return name


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


def resource_members(payload: bytes) -> list[tuple[str, int, int]]:
    """Each session-resource document's path and byte span, in rendered order."""
    span = spans(payload).get("Session Resources")
    if not span:
        return []
    start, end = span
    hits = [
        (match.start() + 1, match.group(1).decode("utf-8", "replace"))
        for match in MEMBER.finditer(payload, start, end)
    ]
    return [
        (path, offset, hits[index + 1][0] if index + 1 < len(hits) else end)
        for index, (offset, path) in enumerate(hits)
    ]


def history_members(payload: bytes) -> list[str]:
    """The rendered history member labels, in document order."""
    span = spans(payload).get("Session History")
    if not span:
        return []
    return [
        item.decode("utf-8", "replace")
        for item in HISTORY_MEMBER.findall(payload[span[0] : span[1]])
    ]


def oldest_turn(labels: list[str]) -> str | None:
    """The oldest rendered turn label, ignoring the always-present request."""
    return next((label for label in labels if label.startswith("Turn ")), None)


def snippet(payload: bytes, offset: int, width: int = 70) -> str:
    """A short single-line rendering of the bytes following ``offset``."""
    text = payload[offset : offset + width].decode("utf-8", "replace")
    return text.replace("\n", "\\n").replace("\r", "")


def analyse(previous_path: Path, current_path: Path) -> dict:
    """Attribute one payload pair to its breaking document or history mechanism."""
    previous = previous_path.read_bytes()
    current = current_path.read_bytes()
    shared = shared_prefix_length(previous, current)
    section = section_at(current, shared)

    previous_map = {path: (start, end) for path, start, end in resource_members(previous)}
    current_map = {path: (start, end) for path, start, end in resource_members(current)}
    added = [path for path in current_map if path not in previous_map]
    removed = [path for path in previous_map if path not in current_map]
    changed = []
    for path, (start, end) in current_map.items():
        if path not in previous_map:
            continue
        previous_start, previous_end = previous_map[path]
        before = previous[previous_start:previous_end]
        after = current[start:end]
        if before != after:
            offset = shared_prefix_length(before, after)
            changed.append(
                {
                    "path": path,
                    "break": start + offset,
                    "delta": len(after) - len(before),
                    "snippet": snippet(current, start + offset),
                }
            )
    changed.sort(key=lambda item: item["break"])

    previous_labels = history_members(previous)
    current_labels = history_members(current)
    old_turn = oldest_turn(previous_labels)
    new_turn = oldest_turn(current_labels)
    dropped = [label for label in previous_labels if label not in current_labels]

    if section == "Session History":
        if old_turn != new_turn:
            cause = f"retention front truncation ({old_turn} -> {new_turn})"
        elif dropped:
            cause = f"history removal ({', '.join(dropped[:2])})"
        else:
            cause = "history append (benign)"
    elif section == "Session Resources":
        labels = added + [item["path"] for item in changed]
        cause = f"resource break: {', '.join(labels[:2]) or 'roster only'}"
    else:
        cause = f"{section} changed"

    return {
        "pair": f"{previous_path.parent.name}->{current_path.parent.name}",
        "shared": shared,
        "share": shared / len(current) if current else 0.0,
        "size": len(current),
        "cause": cause,
        "added": added,
        "removed": removed,
        "changed": changed,
        "dropped": dropped,
    }


def report(label: str, rows: list[dict], show: int) -> None:
    """Print the share profile, the roster changes, and the resource attribution."""
    shares = [row["share"] for row in rows]
    print(f"\n## {label} ({len(rows)} pairs)")
    print(
        f"byte share: mean {statistics.mean(shares):.1%}"
        f" | median {statistics.median(shares):.1%}"
        f" | min {min(shares):.1%} | max {max(shares):.1%}"
    )
    census: dict[str, int] = {}
    for row in rows:
        head = row["cause"].split(":")[0].split(" (")[0]
        census[head] = census.get(head, 0) + 1
    print(
        "causes: "
        + ", ".join(
            f"{name} {count}" for name, count in sorted(census.items(), key=lambda kv: -kv[1])
        )
    )

    roster_changes = [row for row in rows if row["added"] or row["removed"]]
    if roster_changes:
        print(f"roster changed in {len(roster_changes)} pairs:")
        for row in roster_changes[:show]:
            detail = f"added {row['added']}" if row["added"] else f"removed {row['removed']}"
            print(f"  {row['pair']}  {detail}")
    else:
        print("roster: stable for the whole session")

    broken = sorted(
        [row for row in rows if row["changed"]],
        key=lambda row: row["changed"][0]["break"],
    )
    if broken:
        print(f"resource break: {len(broken)} pairs, earliest break first")
        for row in broken[:show]:
            item = row["changed"][0]
            recoverable = item["break"] / row["size"]
            print(
                f"  {row['pair']:<9} share {row['share']:>6.1%}"
                f" | {item['path']} differs at {recoverable:>6.1%}"
                f" ({item['break']:,} B, {item['delta']:+,} B)"
            )
            print(f"            {item['snippet']}")

    history = [
        row for row in rows if row["cause"].startswith(("retention", "history removal"))
    ]
    if history:
        print(f"history break: {len(history)} pairs")
        for row in history[:show]:
            print(f"  {row['pair']:<9} share {row['share']:>6.1%} | {row['cause']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions-dir", default=".teddy/sessions")
    parser.add_argument("--only", default=None, help="session name substring")
    parser.add_argument("--min-payloads", type=int, default=3)
    parser.add_argument("--show", type=int, default=8, help="attributions per section")
    args = parser.parse_args()

    selected: list[tuple[int, Path]] = []
    for session in sorted(Path(args.sessions_dir).iterdir()):
        if not session.is_dir() or (args.only and args.only not in session.name):
            continue
        turns = sorted(
            (
                child
                for child in session.iterdir()
                if child.is_dir()
                and child.name.isdigit()
                and (child / "input.md").exists()
            ),
            key=lambda child: int(child.name),
        )
        if len(turns) >= args.min_payloads:
            selected.append((len(turns), session))

    for count, session in selected:
        payloads = sorted(
            (
                child / "input.md"
                for child in session.iterdir()
                if child.is_dir()
                and child.name.isdigit()
                and (child / "input.md").exists()
            ),
            key=lambda path: int(path.parent.name),
        )
        rows = [
            analyse(previous, current)
            for previous, current in zip(payloads, payloads[1:])
        ]
        if rows:
            report(f"{session.name} [{count} payloads]", rows, args.show)


if __name__ == "__main__":
    main()
