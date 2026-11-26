#!/usr/bin/env python3
"""Attribute a mid-history hole to retention or to the token budget by position.

Status pruning explains a hole whose own turn carried a non-green plan or a
failed report. The remaining hole - a green plan with a successful report - can
only come from retention or from the global token budget, and the two choose
different victims: retention drops the oldest turn ids past its band, while the
budget drops the largest turn-scope files first. Position therefore separates
them without a second size estimate.

The band is reconstructed from the artefacts. ``prune()`` runs status pruning,
then retention, then the budget, and retention counts only the turn ids that
still hold a SELECTED turn-scope item. A preserved turn lives in
``session.context``, so it never occupies a slot. That published manifest yields
the exempt set, the plan and report status lines yield the status-pruned set,
and the newest ``max(1, limit - retention_batch + 1)`` of what remains is the
band. Nothing is deselected while that remainder is at or below ``limit``.

One approximation is stated rather than hidden: the live set is the previous
payload's rendered turns, because that is what the current assembly inherited,
while pruning also sees the files the current turn gathered. Every label is
printed beside the band boundary so the verdict stays auditable.

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
HISTORY_LINE = re.compile(r"^### Turn (\d+): (?:Plan|Report)$")
TURN_PATH = re.compile(r"/(\d{1,3})/(?:plan|report)\.md$")
PLAN_STATUS = "- **Status:**"
REPORT_STATUS = "- **Overall Status:**"
GREEN = "ON-TRACK 🟢"
PROJECT_CONTEXT = b"# Project Context\n"
RUNTIME_MARKER = b"\n## Runtime\n"
FENCE_CHARS = ("`", "~")
MISSING = ("no file", "absent")
VALIDATION_FAILED = "Validation Failed"


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
                if line.rstrip(b"\r\n") == ("## " + name).encode():
                    found.append((offset, name))
        offset += len(line)
    return found


def history_body(payload: bytes) -> bytes:
    """The history section's bytes, bounded by the next real heading."""
    located = marks(payload)
    for index, (offset, name) in enumerate(located):
        if name != "Session History":
            continue
        end = located[index + 1][0] if index + 1 < len(located) else len(payload)
        return payload[offset:end]
    return b""


def outside_fence_lines(body: bytes) -> list[str]:
    """Every line of a section that sits outside a fenced block."""
    kept: list[str] = []
    fence = ""
    for line in body.decode("utf-8", "replace").splitlines():
        stripped = line.strip()
        char = stripped[:1]
        run = len(stripped) - len(stripped.lstrip(char)) if char else 0
        if char and char in FENCE_CHARS and run >= 3:
            if not fence:
                fence = char * run
            elif char == fence[:1] and run >= len(fence) and stripped == char * run:
                fence = ""
            continue
        if not fence:
            kept.append(line)
    return kept


def rendered_ids(payload_path: Path) -> list[int]:
    """The turn ids whose plan or report the payload renders."""
    if not payload_path.exists():
        return []
    found: set[int] = set()
    for line in outside_fence_lines(history_body(payload_path.read_bytes())):
        match = HISTORY_LINE.match(line)
        if match:
            found.add(int(match.group(1)))
    return sorted(found)


def is_shipped_layout(payload: bytes) -> bool:
    """Whether the payload carries the constant header and a runtime tail."""
    return payload.startswith(PROJECT_CONTEXT) and RUNTIME_MARKER in payload


def header_value(path: Path, prefix: str) -> str:
    """The value of one header line, or a marker when it is absent."""
    if not path.exists():
        return "no file"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return "absent"


def preserved_ids(session: Path) -> set[int]:
    """Turn ids a session manifest holds as a prune-exempt session resource."""
    manifest = session / "session.context"
    if not manifest.exists():
        return set()
    found: set[int] = set()
    for line in manifest.read_text(encoding="utf-8").splitlines():
        entry = line.strip().replace("\\", "/")
        if not entry or entry.startswith("#") or entry.endswith(".context"):
            continue
        match = TURN_PATH.search(entry)
        if match:
            found.add(int(match.group(1)))
    return found


def status_state(turn_dir: Path) -> str:
    """The status label pruning would attach, or green when it would not fire."""
    report = header_value(turn_dir / "report.md", REPORT_STATUS)
    plan = header_value(turn_dir / "plan.md", PLAN_STATUS)
    if report == VALIDATION_FAILED:
        return "status: validation"
    if plan not in MISSING and plan != GREEN:
        return "status: failure"
    return "green"


def band(live: list[int], limit: int, batch: int) -> int | None:
    """The oldest turn id retention keeps out of the live set."""
    ordered = sorted(live)
    if not ordered or len(ordered) <= limit:
        return ordered[0] if ordered else None
    depth = max(1, limit - batch + 1)
    return ordered[-depth:][0]


def label(hole: int, band_start: int | None, exempt: set[int], state: str) -> str:
    """Name the mechanism that owns one hole, by condition then by position."""
    if hole in exempt:
        return "preserved (anomaly)"
    if state != "green":
        return state
    if band_start is None or hole < band_start:
        return "green: retention"
    return "green: budget"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions-dir", default=".teddy/sessions")
    parser.add_argument("--limit", type=int, default=10, help="max_turns_retention")
    parser.add_argument("--batch", type=int, default=5, help="retention_batch")
    parser.add_argument("--show", type=int, default=14, help="detail lines")
    args = parser.parse_args()

    assemblies = 0
    holes_seen = 0
    tally: dict[str, int] = {}
    detail: list[str] = []

    for session in sorted(Path(args.sessions_dir).iterdir()):
        if not session.is_dir():
            continue
        turns = sorted(
            (child for child in session.iterdir() if child.is_dir() and child.name.isdigit()),
            key=lambda child: int(child.name),
        )
        paths = {int(turn.name): turn for turn in turns}
        exempt = preserved_ids(session)
        numbers = sorted(paths)
        for index, number in enumerate(numbers):
            if index == 0:
                continue
            current = paths[number]
            previous = paths[numbers[index - 1]]
            payload_path = current / "input.md"
            previous_payload = previous / "input.md"
            if not payload_path.exists() or not previous_payload.exists():
                continue
            if not (
                is_shipped_layout(payload_path.read_bytes())
                and is_shipped_layout(previous_payload.read_bytes())
            ):
                continue
            before = rendered_ids(previous_payload)
            after = rendered_ids(payload_path)
            if not before or not after:
                continue
            assemblies += 1
            floor = min(after)
            holes = [value for value in before if value not in after and value > floor]
            if not holes:
                continue
            live = [
                value
                for value in before
                if value not in exempt and value in paths and status_state(paths[value]) == "green"
            ]
            band_start = band(live, args.limit, args.batch)
            for hole in holes:
                state = status_state(paths[hole]) if hole in paths else "green"
                name = label(hole, band_start, exempt, state)
                tally[name] = tally.get(name, 0) + 1
                holes_seen += 1
                if name.startswith("green") and len(detail) < args.show:
                    detail.append(
                        f"  {session.name[:26]} turn {number:02d} hole {hole:02d}"
                        f" band {band_start if band_start is not None else 'none'}"
                        f" live {len(live)} -> {name}"
                    )

    green_total = sum(
        count for name, count in tally.items() if name.startswith("green")
    )
    print("== verdict ==")
    print(f"shipped-layout assemblies {assemblies}")
    print(f"mid-history holes {holes_seen} | green holes {green_total}")
    print(f"retention {args.limit} / batch {args.batch}")
    print("\n== holes by mechanism ==")
    for name, count in sorted(tally.items(), key=lambda item: -item[1]):
        print(f"  {count:>4}  {name}")
    print("\n== green hole detail ==")
    for line in detail or ["  none"]:
        print(line)


if __name__ == "__main__":
    main()
