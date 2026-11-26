#!/usr/bin/env python3
"""Price demoting an edited document out of the early resource section.

Session resources render ahead of the append-only history, so one edited
document forfeits every cached history byte behind it, on every turn it
changes. This simulates demoting a document after its first observed change:
from then on it renders at the very end of the payload, where a change costs
nothing behind it. Its bytes move rather than disappear, so the share
denominator stays honest.

Documents are read through reorder.documents, whose separator split is already
proven on this corpus, and prefixes through levers.shared_prefix_length.

Read-only: it never writes into a session.
"""

from __future__ import annotations

import argparse
import statistics
from pathlib import Path

from levers import shared_prefix_length
from reorder import documents


def doc_map(payload: bytes) -> dict[str, bytes]:
    """Each resource document's rendered block, keyed by path."""
    found = documents(payload)
    return dict(found[3]) if found else {}


def demote(payload: bytes, evicted: set[str]) -> bytes:
    """Render the demoted documents at the end instead of inside resources."""
    found = documents(payload)
    if found is None or not evicted:
        return payload
    start, end, preamble, blocks = found
    kept = [block for path, block in blocks if path not in evicted]
    moved = [block for path, block in blocks if path in evicted]
    early = payload[:start] + preamble + b"".join(kept) + payload[end:]
    return early + b"".join(moved)


def measure(payloads: list[Path]) -> dict[str, list[float]]:
    """Mean prefix share under the shipped policy and under demotion."""
    raw = [payload.read_bytes() for payload in payloads]
    docs = [doc_map(payload) for payload in raw]
    evicted: set[str] = set()
    result: dict[str, list[float]] = {"current": [], "evict": []}
    for index in range(1, len(raw)):
        shipped = shared_prefix_length(raw[index - 1], raw[index])
        left = demote(raw[index - 1], evicted)
        right = demote(raw[index], evicted)
        demoted = shared_prefix_length(left, right)
        size = len(raw[index])
        result["current"].append(shipped / size)
        result["evict"].append(demoted / len(right))
        for path, block in docs[index].items():
            if docs[index - 1].get(path, block) != block:
                evicted.add(path)
    return result


def report(label: str, payloads: list[Path], result: dict[str, list[float]]) -> None:
    """Print both means, the delta, and how many documents got demoted."""
    if not result["current"]:
        return
    shipped = statistics.mean(result["current"])
    demoted = statistics.mean(result["evict"])
    docs = doc_map(payloads[-1].read_bytes())
    churned = set()
    for index in range(1, len(payloads)):
        before = doc_map(payloads[index - 1].read_bytes())
        for path, block in doc_map(payloads[index].read_bytes()).items():
            if before.get(path, block) != block:
                churned.add(path)
    print(f"\n## {label} ({len(result['current'])} pairs)")
    print(f"shipped   mean {shipped:>6.1%}")
    print(f"evict     mean {demoted:>6.1%} | delta {demoted - shipped:+.1%}")
    print(f"documents: {len(docs)} rendered, {len(churned)} changed at least once")


def main() -> None:
    parser = argparse.ArgumentParser(description="Price eviction-on-edit.")
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
