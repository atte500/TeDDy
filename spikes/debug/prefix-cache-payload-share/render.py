#!/usr/bin/env python3
"""Report where a path renders and which members a section holds.

An admission rule is only understood once the rendered payload is read: a path
held in one scope can still render in another section, and a turn missing from
the history sequence is easier to name than to infer. This prints every
occurrence of a path fragment with the fence-aware section holding it, then
lists the level-three member headers of the requested sections so a hole in the
history sequence is visible rather than argued.

Section boundaries come from levers.spans, which is fence-aware: a quoted
document cannot invent a section here.

Read-only: it never writes into a session or a plan.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from levers import spans

MEMBER = b"### "


def holding_section(payload: bytes, offset: int) -> str:
    """Name the section whose span contains ``offset``."""
    name = "header"
    for section, (start, _end) in sorted(
        spans(payload).items(), key=lambda item: item[1][0]
    ):
        if start > offset:
            break
        name = section
    return name


def occurrences(payload: bytes, needle: str) -> list[tuple[str, int]]:
    """Every occurrence of ``needle`` paired with the section holding it."""
    hits: list[tuple[str, int]] = []
    start = 0
    while True:
        offset = payload.find(needle.encode("utf-8"), start)
        if offset < 0:
            return hits
        hits.append((holding_section(payload, offset), offset))
        start = offset + 1


def members(payload: bytes, section: str) -> list[str]:
    """The level-three member headers rendered inside one section."""
    span = spans(payload).get(section)
    if not span:
        return []
    return [
        line.decode("utf-8", "replace")
        for line in payload[span[0] : span[1]].splitlines()
        if line.startswith(MEMBER)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", required=True, help="path to an input.md")
    parser.add_argument("--needle", action="append", default=[], help="repeatable")
    parser.add_argument(
        "--sections",
        default="Session Resources,Session History",
        help="comma-separated section names to list members for",
    )
    args = parser.parse_args()

    payload = Path(args.payload).read_bytes()
    print(f"payload: {args.payload} ({len(payload):,} B)")
    for section, (start, end) in sorted(
        spans(payload).items(), key=lambda item: item[1][0]
    ):
        print(f"  {section:<20} {start:>8,}..{end:>8,}")

    for needle in args.needle:
        hits = occurrences(payload, needle)
        where = ", ".join(f"{section}@{offset:,}" for section, offset in hits) or "absent"
        print(f"needle {needle!r}: {len(hits)} hits -> {where}")

    for name in args.sections.split(","):
        found = members(payload, name.strip())
        print(f"members of {name.strip()} ({len(found)}):")
        for line in found:
            print(f"  {line}")
    print()


if __name__ == "__main__":
    main()
