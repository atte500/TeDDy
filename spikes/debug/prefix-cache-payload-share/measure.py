#!/usr/bin/env python3
"""Measure provider prefix-cache share across recorded context payloads.

Each ``.teddy/sessions/<name>/NN/input.md`` is the exact text a provider
received. For every consecutive pair this reports the shared leading byte count
(what a prefix cache serves for free), that share of the later payload, and
which payload section holds the first differing byte.

Byte offsets are used throughout, never decoded character offsets, because the
payloads carry multi-byte emoji and a character offset would misattribute the
divergence section.

Read-only: it never writes into a session.
"""

from __future__ import annotations

import argparse
import statistics
from pathlib import Path

SECTION_NAMES = (
    "System Information",
    "Session Resources",
    "Session History",
    "Git Status",
    "Project Structure",
    "Resource Contents",
    "Runtime",
)


def section_marks(payload: bytes) -> list[tuple[int, str]]:
    """Return each known section heading's byte offset, ordered by position."""
    marks: list[tuple[int, str]] = []
    for name in SECTION_NAMES:
        offset = payload.find(f"\n## {name}\n".encode())
        if offset >= 0:
            marks.append((offset, name))
    marks.sort()
    return marks


def section_at(payload: bytes, offset: int) -> str:
    """Name the section holding ``offset`` (``header`` before the first one)."""
    name = "header"
    for mark_offset, mark_name in section_marks(payload):
        if mark_offset > offset:
            break
        name = mark_name
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


def payload_paths(session: Path) -> list[Path]:
    """The session's ``input.md`` payloads, in turn order."""
    turns = [
        child
        for child in session.iterdir()
        if child.is_dir() and child.name.isdigit() and (child / "input.md").exists()
    ]
    return [turn / "input.md" for turn in sorted(turns, key=lambda t: int(t.name))]


def measure(session: Path) -> list[dict]:
    """Measure every consecutive payload pair of one session."""
    rows: list[dict] = []
    paths = payload_paths(session)
    for previous, current in zip(paths, paths[1:]):
        previous_bytes = previous.read_bytes()
        current_bytes = current.read_bytes()
        shared = shared_prefix_length(previous_bytes, current_bytes)
        rows.append(
            {
                "pair": f"{previous.parent.name}->{current.parent.name}",
                "shared": shared,
                "share": shared / len(current_bytes) if current_bytes else 0.0,
                "grew": len(current_bytes) - len(previous_bytes),
                "dies_in": section_at(current_bytes, shared),
            }
        )
    return rows


def summarize(label: str, rows: list[dict], show_pairs: int) -> None:
    """Print one session's or the aggregate's share profile and death census."""
    shares = [row["share"] for row in rows]
    if not shares:
        return
    deaths: dict[str, int] = {}
    for row in rows:
        deaths[row["dies_in"]] = deaths.get(row["dies_in"], 0) + 1
    floor = statistics.quantiles(shares, n=10)[0] if len(shares) > 1 else shares[0]
    print(f"\n## {label} ({len(rows)} pairs)")
    print(
        f"mean {statistics.mean(shares):.1%} | median {statistics.median(shares):.1%}"
        f" | min {min(shares):.1%} | max {max(shares):.1%} | p10 {floor:.1%}"
    )
    census = ", ".join(
        f"{name} {count}"
        for name, count in sorted(deaths.items(), key=lambda kv: -kv[1])
    )
    print(f"first difference in: {census}")
    worst = sorted(rows, key=lambda row: row["share"])[:show_pairs]
    print(f"  {'pair':<9} {'shared':>9} {'share':>7} {'grew':>10}  dies in")
    for row in worst:
        print(
            f"  {row['pair']:<9} {row['shared']:>9,} {row['share']:>6.1%}"
            f" {row['grew']:>+10,}  {row['dies_in']}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions-dir", default=".teddy/sessions")
    parser.add_argument("--top", type=int, default=6, help="sessions with the most payloads")
    parser.add_argument("--only", default=None, help="session name substring")
    parser.add_argument("--min-payloads", type=int, default=2)
    parser.add_argument("--show-pairs", type=int, default=6, help="worst pairs per session")
    args = parser.parse_args()

    sessions_root = Path(args.sessions_dir)
    candidates: list[tuple[int, Path]] = []
    for session in sorted(sessions_root.iterdir()):
        if not session.is_dir():
            continue
        if args.only and args.only not in session.name:
            continue
        count = len(payload_paths(session))
        if count >= args.min_payloads:
            candidates.append((count, session))
    candidates.sort(key=lambda item: item[0], reverse=True)

    selected = candidates if args.only else candidates[: args.top]
    overall: list[dict] = []
    for count, session in selected:
        rows = measure(session)
        overall.extend(rows)
        summarize(f"{session.name} [{count} payloads]", rows, args.show_pairs)

    summarize(f"All {len(selected)} sessions", overall, args.show_pairs)


if __name__ == "__main__":
    main()
