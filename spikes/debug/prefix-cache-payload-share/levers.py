#!/usr/bin/env python3
"""Measure which levers actually govern prefix-cache share.

Sections are located with fence awareness: an embedded resource, plan, or spec
document carries its own ``## `` headings inside a dynamic code fence, so a
heading only marks a section when it sits outside a fence. Without that rule a
quoted document invents sections and every later attribution shifts.

Per session this reports three means over consecutive payload pairs:

* measured, the bytes a provider serves from cache today;
* stable resources, recomputed as if the session-resource documents had stayed
  byte identical, which prices a mutable working document sitting in the
  byte-stable prefix;
* swapped order, recomputed with Session History ahead of Session Resources,
  which prices the current section order itself. Ordering never changes payload
  size, so the comparison is exact rather than modelled.

The provider's own reported hit rate is printed beside the measured share, so
the byte metric can be checked rather than trusted.

Read-only: it never writes into a session.
"""

from __future__ import annotations

import argparse
import statistics
from pathlib import Path

import yaml

HEADINGS = (
    "Session Resources",
    "Session History",
    "Git Status",
    "Project Structure",
    "Resource Contents",
    "Runtime",
)
SWAPPED = (
    "Session History",
    "Session Resources",
    "Git Status",
    "Project Structure",
    "Resource Contents",
    "Runtime",
)
HEADER_KEY = "__header__"


def marks(payload: bytes) -> list[tuple[int, str]]:
    """Byte offsets of the real section headings, in document order.

    A heading inside a fenced block belongs to embedded content, never to the
    payload's own structure, so it is skipped.
    """
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
    """Each section's byte span, bounded by the next real heading."""
    located = marks(payload)
    return {
        name: (offset, located[index + 1][0] if index + 1 < len(located) else len(payload))
        for index, (offset, name) in enumerate(located)
    }


def blocks(payload: bytes) -> dict[str, bytes]:
    """The header and every section block, keyed by section name."""
    located = marks(payload)
    header_end = located[0][0] if located else len(payload)
    pieces = {HEADER_KEY: payload[:header_end]}
    for index, (offset, name) in enumerate(located):
        end = located[index + 1][0] if index + 1 < len(located) else len(payload)
        pieces[name] = payload[offset:end]
    return pieces


def reorder(payload: bytes, order: tuple[str, ...]) -> bytes:
    """The same payload bytes with its section blocks in a different order."""
    pieces = blocks(payload)
    parts = [pieces[HEADER_KEY]]
    parts.extend(pieces.get(name, b"") for name in order)
    return b"".join(parts)


def shared_prefix_length(left: bytes, right: bytes) -> int:
    """Binary-search the first differing byte between two byte strings."""
    low, high = 0, min(len(left), len(right))
    while low < high:
        middle = (low + high + 1) // 2
        if left[:middle] == right[:middle]:
            low = middle
        else:
            high = middle - 1
    return low


def section_at(payload: bytes, offset: int) -> str:
    """Name the section holding ``offset`` (``header`` before the first one)."""
    name = "header"
    ordered = sorted(spans(payload).items(), key=lambda item: item[1][0])
    for section, (start, _end) in ordered:
        if start > offset:
            break
        name = section
    return name


def history_shared(previous: bytes, current: bytes) -> int:
    """Bytes of the history section the two payloads still share."""
    before = spans(previous).get("Session History")
    after = spans(current).get("Session History")
    if not before or not after:
        return 0
    return shared_prefix_length(
        previous[before[0] : before[1]], current[after[0] : after[1]]
    )


def stable_resource_prefix(previous: bytes, current: bytes) -> int:
    """Prefix length assuming the session-resource documents had matched.

    With the resources identical, every byte ahead of the history section is
    shared, and the prefix then continues into the history section up to that
    section's own first difference. Everything else is held as observed.
    """
    start = spans(current).get("Session History")
    if not start:
        return shared_prefix_length(previous, current)
    return min(len(current), start[0] + history_shared(previous, current))


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


def analyse(previous_path: Path, current_path: Path) -> dict:
    """Measure one payload pair and both counterfactuals."""
    previous = previous_path.read_bytes()
    current = current_path.read_bytes()
    size = len(current)
    measured = shared_prefix_length(previous, current)
    stable = stable_resource_prefix(previous, current)
    swapped = shared_prefix_length(reorder(previous, SWAPPED), reorder(current, SWAPPED))
    cached, prompt = telemetry(current_path.parent)
    return {
        "pair": f"{previous_path.parent.name}->{current_path.parent.name}",
        "grew": size - len(previous),
        "measured_share": measured / size if size else 0.0,
        "stable_share": min(stable, size) / size if size else 0.0,
        "swapped_share": min(swapped, size) / size if size else 0.0,
        "cause": section_at(current, measured),
        "cached": cached,
        "prompt": prompt,
    }


def report(label: str, rows: list[dict], show: int) -> None:
    """Print the three means, the provider's hit rate, and the worst pairs."""
    measured = [row["measured_share"] for row in rows]
    stable = [row["stable_share"] for row in rows]
    swapped = [row["swapped_share"] for row in rows]
    print(f"\n## {label} ({len(rows)} pairs)")
    print(
        f"measured         mean {statistics.mean(measured):>6.1%}"
        f" | median {statistics.median(measured):>6.1%} | min {min(measured):>6.1%}"
    )
    print(
        f"stable resources mean {statistics.mean(stable):>6.1%}"
        f" | delta {statistics.mean(stable) - statistics.mean(measured):+.1%}"
    )
    print(
        f"swapped order    mean {statistics.mean(swapped):>6.1%}"
        f" | delta {statistics.mean(swapped) - statistics.mean(measured):+.1%}"
    )
    hits = [row["cached"] / row["prompt"] for row in rows if row["prompt"] > 0]
    if hits:
        print(
            f"provider hit rate mean {statistics.mean(hits):>6.1%}"
            f" | median {statistics.median(hits):>6.1%} over {len(hits)} turns"
        )
    census: dict[str, int] = {}
    for row in rows:
        census[row["cause"]] = census.get(row["cause"], 0) + 1
    print(
        "first difference by section: "
        + ", ".join(
            f"{name} {count}"
            for name, count in sorted(census.items(), key=lambda item: -item[1])
        )
    )
    header = f"  {'pair':<9} {'meas':>6} {'stable':>6} {'swap':>6} {'grew':>10}"
    print(header)
    for row in sorted(rows, key=lambda item: item["measured_share"])[:show]:
        print(
            f"  {row['pair']:<9} {row['measured_share']:>5.1%}"
            f" {row['stable_share']:>6.1%} {row['swapped_share']:>6.1%}"
            f" {row['grew']:>+10,}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions-dir", default=".teddy/sessions")
    parser.add_argument("--only", default=None, help="session name substring")
    parser.add_argument("--min-payloads", type=int, default=3)
    parser.add_argument("--show", type=int, default=8, help="worst pairs per session")
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
        rows = [
            analyse(previous, current)
            for previous, current in zip(payloads, payloads[1:])
        ]
        if rows:
            report(f"{session.name} [{len(payloads)} payloads]", rows, args.show)


if __name__ == "__main__":
    main()
