#!/usr/bin/env python3
"""Price a stability-ordered Session Resources roster.

The session manifest is written as a sorted set, so the roster order is
alphabetical rather than chosen. This measures what a stability-ordered roster
would buy: documents that changed least render first, so the earliest volatile
document sits as close to Session History as possible.

Documents are ranked by how often they changed in the payloads recorded BEFORE
the pair being graded, because that is what a shipped implementation could know.
A ranking built from the whole session would report a share no code can reach.

Section boundaries come from levers.py, which is fence-aware: an embedded
document quoting a section heading cannot invent a section here.

Known limitation: a resource body containing the exact separator line would be
split into two documents. Nothing in the corpus does, and a mis-split can only
worsen the reordered share, never flatter it.

Read-only: it never writes into a session.
"""

from __future__ import annotations

import argparse
import statistics
from pathlib import Path

from levers import shared_prefix_length, spans

SPLIT = b"\n---\n### ["
UNSEEN = 1 << 30


def documents(payload: bytes) -> tuple[int, int, bytes, list[tuple[str, bytes]]] | None:
    """The resources section preamble plus one block per document, in order."""
    span = spans(payload).get("Session Resources")
    if not span:
        return None
    start, end = span
    parts = payload[start:end].split(SPLIT)
    if len(parts) < 2:
        return None
    blocks = [
        (part.split(b"]", 1)[0].decode("utf-8", "replace"), SPLIT + part)
        for part in parts[1:]
    ]
    return start, end, parts[0], blocks


def reorder(payload: bytes, rank) -> bytes:
    """The same payload with its resource documents ordered by rank."""
    found = documents(payload)
    if found is None or rank is None:
        return payload
    start, end, preamble, blocks = found
    ordered = sorted(blocks, key=lambda block: rank(block[0]))
    body = preamble + b"".join(block for _path, block in ordered)
    return payload[:start] + body + payload[end:]


def change_deltas(payloads: list[bytes]) -> list[dict[str, int]]:
    """Which documents changed in each payload, relative to its predecessor."""
    deltas: list[dict[str, int]] = []
    previous: dict[str, bytes] = {}
    for payload in payloads:
        found = documents(payload)
        current = dict(found[3]) if found else {}
        deltas.append(
            {
                path: 1
                for path, block in current.items()
                if path in previous and previous[path] != block
            }
        )
        previous = current
    return deltas


def measure(payloads: list[Path]) -> dict[str, list[float]]:
    """Mean prefix share under the shipped order and both reorder policies."""
    raw = [payload.read_bytes() for payload in payloads]
    deltas = change_deltas(raw)
    totals: dict[str, int] = {}
    result: dict[str, list[float]] = {"current": [], "stable": [], "volatile": []}
    for index in range(1, len(raw)):
        for path in deltas[index]:
            totals[path] = totals.get(path, 0) + 1
        seen = dict(totals)
        policies = (
            ("current", None),
            ("stable", lambda path: seen.get(path, UNSEEN)),
            ("volatile", lambda path: -seen.get(path, UNSEEN)),
        )
        for name, rank in policies:
            left = reorder(raw[index - 1], rank)
            right = reorder(raw[index], rank)
            shared = shared_prefix_length(left, right)
            result[name].append(shared / len(right) if right else 0.0)
    return result


def report(label: str, payloads: list[Path], result: dict[str, list[float]]) -> None:
    """Print the three means and the roster the final payload would receive."""
    if not result["current"]:
        return
    baseline = statistics.mean(result["current"])
    print(f"\n## {label} ({len(result['current'])} pairs)")
    for name, values in result.items():
        mean = statistics.mean(values)
        delta = "" if name == "current" else f" | delta {mean - baseline:+.1%}"
        print(f"{name:<9} mean {mean:>6.1%}{delta}")
    found = documents(payloads[-1].read_bytes())
    if found and len(payloads) > 1:
        deltas = change_deltas([payload.read_bytes() for payload in payloads])
        totals: dict[str, int] = {}
        for delta in deltas[:-1]:
            for path in delta:
                totals[path] = totals.get(path, 0) + 1
        ordered = sorted(found[3], key=lambda block: totals.get(block[0], UNSEEN))
        print(f"stable-first renders {ordered[0][0]} first")
        print(f"              and {ordered[-1][0]} last")


def main() -> None:
    parser = argparse.ArgumentParser(description="Price a reordered resource roster.")
    parser.add_argument("--sessions-dir", default=".teddy/sessions")
    parser.add_argument("--only", default=None, help="session name substring")
    parser.add_argument("--min-payloads", type=int, default=4)
    args = parser.parse_args()

    for session in sorted(Path(args.sessions_dir).iterdir()):
        if not session.is_dir() or (args.only and args.only not in session.name):
            continue
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
        if len(payloads) < args.min_payloads:
            continue
        report(f"{session.name} [{len(payloads)} payloads]", payloads, measure(payloads))


if __name__ == "__main__":
    main()
