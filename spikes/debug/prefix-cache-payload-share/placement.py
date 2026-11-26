#!/usr/bin/env python3
"""Print the rendered rosters of one payload and where needles land.

A preserved turn is admitted to the session manifest, but history headers strip
raw paths, so a path needle can never hit the history section. Placement is
therefore read as a roster comparison: which resource documents render, and
which turn headers the history sequence still contains.

Headers are matched by shape, so an embedded document's own subheadings stay out
of both lists. Sections come from levers.spans, which is fence-aware.

Read-only: it never writes into a session or a plan.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from levers import spans

RESOURCE_HEADER = re.compile(r"^### \[([^\]]+)\]\([^)]*\)$")
HISTORY_HEADER = re.compile(
    r"^### (Initial Request|Turn \d+: (?:Plan|Report|Execution Report))$"
)


def holding_section(payload: bytes, offset: int) -> str:
    """Name the section whose span contains the offset."""
    name = "header"
    for section, (start, _end) in sorted(
        spans(payload).items(), key=lambda item: item[1][0]
    ):
        if start > offset:
            break
        name = section
    return name


def hits(payload: bytes, needle: str) -> list[tuple[str, int]]:
    """Every occurrence of the needle paired with its holding section."""
    found: list[tuple[str, int]] = []
    encoded = needle.encode("utf-8")
    start = 0
    while True:
        offset = payload.find(encoded, start)
        if offset < 0:
            return found
        found.append((holding_section(payload, offset), offset))
        start = offset + len(encoded)


def headers(payload: bytes, section: str, pattern: re.Pattern[str]) -> list[str]:
    """The header lines of one section that match the expected shape."""
    span = spans(payload).get(section)
    if not span:
        return []
    body = payload[span[0] : span[1]].decode("utf-8", "replace")
    return [line for line in body.splitlines() if pattern.match(line)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", required=True, help="path to an input.md")
    parser.add_argument("--needle", action="append", default=[], help="repeatable")
    args = parser.parse_args()

    payload = Path(args.payload).read_bytes()
    print(f"payload {args.payload} ({len(payload):,} B)")
    for section, (start, end) in sorted(
        spans(payload).items(), key=lambda item: item[1][0]
    ):
        print(f"  span {section:<18} {start:>7,}..{end:>7,}")

    for needle in args.needle:
        found = hits(payload, needle)
        where = ", ".join(f"{section}@{offset:,}" for section, offset in found) or "absent"
        print(f"needle {needle}: {len(found)} -> {where}")

    resources = headers(payload, "Session Resources", RESOURCE_HEADER)
    print(f"resource roster ({len(resources)}):")
    for line in resources:
        print(f"  {line}")

    history = headers(payload, "Session History", HISTORY_HEADER)
    print(f"history roster ({len(history)}):")
    for line in history:
        print(f"  {line}")


if __name__ == "__main__":
    main()
