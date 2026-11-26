#!/usr/bin/env python3
"""Attribute each prefix break to a mechanism and grade retention policies.

For every consecutive pair of recorded ``input.md`` payloads this reports what
changed first: the session-scoped resources, the front of the pruned history, a
turn missing from the middle of the history, or merely the append of a new turn.
It pairs that attribution with the provider's own per-turn cache accounting from
``meta.yaml``, so the byte-share metric can be checked against what the provider
actually served.

A final block grades ``max_turns_retention`` / ``retention_batch`` pairs under a
retention-only model: the history is assumed lost whenever the oldest rendered
turn moves, and every other mechanism is held as observed. That is an upper
bound on what retention tuning alone can recover, never a prediction of the
combined effect.

Read-only: it never writes into a session.
"""

from __future__ import annotations

import argparse
import re
import statistics
from pathlib import Path

import yaml

SECTION_NAMES = (
    "Session Resources",
    "Session History",
    "Git Status",
    "Project Structure",
    "Resource Contents",
    "Runtime",
)
RESOURCE_MEMBER = re.compile(rb"\n### \[([^\]]+)\]")
HISTORY_MEMBER = re.compile(rb"\n### ((?:Turn \d+: (?:Plan|Report))|Initial Request)")
TURN_MARKER = re.compile(rb"\n### Turn \d+: (?:Plan|Report)")


def spans(payload: bytes) -> dict[str, tuple[int, int]]:
    """Return each section's byte span, bounded by the next known heading."""
    marks: list[tuple[int, str]] = []
    for name in SECTION_NAMES:
        offset = payload.find(f"\n## {name}\n".encode())
        if offset >= 0:
            marks.append((offset, name))
    marks.sort()
    result: dict[str, tuple[int, int]] = {}
    for index, (offset, name) in enumerate(marks):
        end = marks[index + 1][0] if index + 1 < len(marks) else len(payload)
        result[name] = (offset, end)
    return result


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


def members(payload: bytes, section: str, pattern: re.Pattern[bytes]) -> list[str]:
    """The member headers rendered inside one section, in document order."""
    span = spans(payload).get(section)
    if not span:
        return []
    found = pattern.findall(payload[span[0] : span[1]])
    return [item.decode("utf-8", "replace") for item in found]


def section_at(payload: bytes, offset: int) -> str:
    """Name the section holding ``offset`` (``header`` before the first one)."""
    name = "header"
    ordered = sorted(spans(payload).items(), key=lambda item: item[1][0])
    for section, (start, _end) in ordered:
        if start > offset:
            break
        name = section
    return name


def first_turn(payload: bytes) -> str | None:
    """The oldest rendered turn label, ignoring the always-present request."""
    for label in members(payload, "Session History", HISTORY_MEMBER):
        if label.startswith("Turn "):
            return label
    return None


def turn_marker_offset(payload: bytes) -> int | None:
    """Byte offset of the first rendered turn, or ``None`` when none renders."""
    span = spans(payload).get("Session History")
    if not span:
        return None
    match = TURN_MARKER.search(payload, span[0], span[1])
    return match.start() if match else None


def history_tail_length(payload: bytes) -> int:
    """Bytes the history section holds from its first turn to its end."""
    span = spans(payload).get("Session History")
    marker = turn_marker_offset(payload)
    if not span or marker is None:
        return 0
    return span[1] - marker


def telemetry(turn_dir: Path) -> tuple[int, int]:
    """The provider's own cached and total prompt token counts for one turn."""
    meta_path = turn_dir / "meta.yaml"
    if not meta_path.exists():
        return 0, 0
    meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
    try:
        return int(meta.get("cached_tokens", 0)), int(meta.get("prompt_tokens", 0))
    except (TypeError, ValueError):
        return 0, 0


def classify(previous: bytes, current: bytes, shared: int) -> str:
    """Name the mechanism that ended the shared prefix."""
    section = section_at(current, shared)
    if section != "Session History":
        return f"{section} changed"
    old_turn = first_turn(previous)
    new_turn = first_turn(current)
    if old_turn != new_turn:
        return "history pruned from the front"
    previous_members = members(previous, "Session History", HISTORY_MEMBER)
    current_members = members(current, "Session History", HISTORY_MEMBER)
    if any(item not in current_members for item in previous_members):
        return "history turn removed mid-section"
    return "history content shifted"


def analyse(previous_path: Path, current_path: Path) -> dict:
    """Attribute one consecutive payload pair and capture what grading needs."""
    previous = previous_path.read_bytes()
    current = current_path.read_bytes()
    shared = shared_prefix_length(previous, current)
    section = section_at(current, shared)
    current_marker = turn_marker_offset(current)
    cached, prompt = telemetry(current_path.parent)
    return {
        "pair": f"{previous_path.parent.name}->{current_path.parent.name}",
        "turn": int(current_path.parent.name),
        "shared": shared,
        "share": shared / len(current) if current else 0.0,
        "grew": len(current) - len(previous),
        "cause": classify(previous, current, shared),
        "cached": cached,
        "prompt": prompt,
        "capped": section != "Session History",
        "marker": current_marker if current_marker is not None else 0,
        "tail": history_tail_length(previous),
        "size": len(current),
        "resources": sorted(
            set(members(current, "Session Resources", RESOURCE_MEMBER))
            - set(members(previous, "Session Resources", RESOURCE_MEMBER))
        ),
    }


def retained_starts(turn_count: int, limit: int, batch: int) -> dict[int, int | None]:
    """Map each payload's turn to the oldest turn its retained history renders."""
    starts: dict[int, int | None] = {1: None}
    retained: list[int] = []
    for turn in range(2, turn_count + 1):
        retained.append(turn - 1)
        if limit > 0 and len(retained) > limit:
            retained = retained[-max(1, limit - batch + 1) :]
        starts[turn] = retained[0] if retained else None
    return starts


def grade(rows: list[dict], limit: int, batch: int) -> float:
    """Mean prefix share if only the retention window were changed."""
    starts = retained_starts(max(row["turn"] for row in rows), limit, batch)
    shares: list[float] = []
    for row in rows:
        folded = (
            row["marker"] + row["tail"]
            if starts[row["turn"]] == starts[row["turn"] - 1]
            else row["marker"]
        )
        predicted = min(row["shared"], folded) if row["capped"] else folded
        shares.append(min(predicted, row["size"]) / row["size"])
    return statistics.mean(shares)


def report(label: str, rows: list[dict], show_pairs: int) -> None:
    """Print the attribution table with the provider's own hit rate beside it."""
    shares = [row["share"] for row in rows]
    causes: dict[str, int] = {}
    for row in rows:
        causes[row["cause"]] = causes.get(row["cause"], 0) + 1
    print(f"\n## {label} ({len(rows)} pairs)")
    print(
        f"byte share: mean {statistics.mean(shares):.1%}"
        f" | median {statistics.median(shares):.1%}"
        f" | min {min(shares):.1%} | max {max(shares):.1%}"
    )
    hits = [row["cached"] / row["prompt"] for row in rows if row["prompt"] > 0]
    if hits:
        print(
            f"provider:   mean {statistics.mean(hits):.1%}"
            f" | median {statistics.median(hits):.1%} over {len(hits)} turns"
        )
    census = ", ".join(
        f"{name} {count}" for name, count in sorted(causes.items(), key=lambda kv: -kv[1])
    )
    print(f"first difference in: {census}")
    print(f"  {'pair':<9} {'share':>7} {'cached':>16} {'cause':<34} grew")
    for row in sorted(rows, key=lambda item: item["share"])[:show_pairs]:
        hit = f"{row['cached']:,}/{row['prompt']:,}" if row["prompt"] else "n/a"
        print(
            f"  {row['pair']:<9} {row['share']:>6.1%} {hit:>16}"
            f" {row['cause']:<34} {row['grew']:+,}"
        )
        if row["resources"]:
            print(f"            added resources: {row['resources']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions-dir", default=".teddy/sessions")
    parser.add_argument("--only", default=None, help="session name substring")
    parser.add_argument("--top", type=int, default=1)
    parser.add_argument("--min-payloads", type=int, default=3)
    parser.add_argument("--show-pairs", type=int, default=12)
    parser.add_argument("--limits", default="0,6,10,14,20")
    parser.add_argument("--batches", default="1,2,5,10")
    args = parser.parse_args()

    candidates: list[tuple[int, Path]] = []
    for session in sorted(Path(args.sessions_dir).iterdir()):
        if not session.is_dir() or (args.only and args.only not in session.name):
            continue
        turns = sorted(
            (child for child in session.iterdir() if child.is_dir() and child.name.isdigit()),
            key=lambda child: int(child.name),
        )
        payloads = [turn for turn in turns if (turn / "input.md").exists()]
        if len(payloads) >= args.min_payloads:
            candidates.append((len(payloads), session))
    candidates.sort(key=lambda item: item[0], reverse=True)
    selected = candidates if args.only else candidates[: args.top]

    limits = [int(value) for value in args.limits.split(",")]
    batches = [int(value) for value in args.batches.split(",")]
    limits_label = ["off" if limit == 0 else str(limit) for limit in limits]

    for count, session in selected:
        turns = sorted(
            (child for child in session.iterdir() if child.is_dir() and child.name.isdigit()),
            key=lambda child: int(child.name),
        )
        payloads = [turn / "input.md" for turn in turns if (turn / "input.md").exists()]
        rows = [analyse(previous, current) for previous, current in zip(payloads, payloads[1:])]
        if not rows:
            continue
        report(f"{session.name} [{count} payloads]", rows, args.show_pairs)
        measured = statistics.mean(row["share"] for row in rows)
        print(f"\n  retention-only grade (measured now: {measured:.1%})")
        print("  ceiling | " + " | ".join(f"batch {b:>2}" for b in batches))
        for limit, label in zip(limits, limits_label):
            cells = " | ".join(f"{grade(rows, limit, batch):>8.1%}" for batch in batches)
            print(f"  {label:>7} | {cells}")


if __name__ == "__main__":
    main()
