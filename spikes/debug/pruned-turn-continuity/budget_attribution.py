#!/usr/bin/env python3
"""Attribute a mid-history removal to the token budget instead of to a status.

Three settings can remove a turn from the middle of the rendered history:
validation-failure pruning when the report says Validation Failed, failure
pruning when a non-green plan is cleaned up after recovery, and the global token
budget, which drops the largest selected turn-scope files until the total fits
auto_pruning.turn_context_threshold. Elimination attributed the measured
green-with-SUCCESS removals to the budget, and this probe turns that elimination
into evidence: it sums the turn-scope files each turn inherited, compares the
total with the threshold, and reports which turns vanished from that assembly.

A turn whose inherited load already exceeds the budget must have been pruned by
it, because no status heuristic can drop a healthy turn and retention removes by
age rather than by size. The estimate mirrors the production characters-over-four
count, so an absolute total is approximate while one well above the threshold
stays decisive and one well below it rules the budget out.

Only assemblies carrying the shipped layout are graded, because the earlier
layouts keep per-turn clock rows in the header and measure nothing useful here.

Read-only: it never writes into a session.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

HEADINGS = (
    "Session Resources",
    "Session History",
    "Git Status",
    "Project Structure",
    "Resource Contents",
    "Runtime",
)
TURN_FILE = re.compile(r"/(\d{1,3})/(?:input|plan|report)\.md$")
HISTORY_LINE = re.compile(r"^### Turn (\d+): (?:Plan|Report)$")
PLAN_STATUS = "- **Status:**"
REPORT_STATUS = "- **Overall Status:**"
CHARS_PER_TOKEN = 4
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
    body = history_body(payload_path.read_bytes())
    found: set[int] = set()
    for line in outside_fence_lines(body):
        match = HISTORY_LINE.match(line)
        if match:
            found.add(int(match.group(1)))
    return sorted(found)


def is_shipped_layout(payload: bytes) -> bool:
    """Whether the payload carries the constant header and a runtime tail."""
    return payload.startswith(b"# Project Context\n") and b"\n## Runtime\n" in payload


def carried_turn_files(turn_dir: Path) -> list[Path]:
    """The existing turn-scope files the turn inherited, deduplicated."""
    manifest = turn_dir / "turn.context"
    if not manifest.exists():
        return []
    found: dict[str, Path] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if not entry or not TURN_FILE.search(entry.replace("\\", "/")):
            continue
        candidate = Path(entry)
        if candidate.is_file():
            found[entry] = candidate
    return list(found.values())


def estimate_tokens(files: list[Path]) -> int:
    """The characters-over-four estimate, summed over the inherited files."""
    total = 0
    for path in files:
        total += len(path.read_text(encoding="utf-8", errors="replace"))
    return total // CHARS_PER_TOKEN


def header_value(path: Path, prefix: str) -> str:
    """The value of one header line, or a marker when it is absent."""
    if not path.exists():
        return "no file"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return "absent"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions-dir", default=".teddy/sessions")
    parser.add_argument("--threshold", type=int, default=50000)
    parser.add_argument("--show", type=int, default=12, help="detail lines to print")
    args = parser.parse_args()

    assemblies = 0
    over_budget: list[str] = []
    drop_counts: dict[str, int] = {}
    detail: list[str] = []
    dropped_total = 0
    dropped_over = 0

    for session in sorted(Path(args.sessions_dir).iterdir()):
        if not session.is_dir():
            continue
        turns = sorted(
            (child for child in session.iterdir() if child.is_dir() and child.name.isdigit()),
            key=lambda child: int(child.name),
        )
        paths = {int(turn.name): turn for turn in turns}
        previous: list[int] | None = None
        for number, turn in paths.items():
            payload_path = turn / "input.md"
            if not payload_path.exists():
                continue
            payload = payload_path.read_bytes()
            rendered = rendered_ids(payload_path)
            if previous is None:
                previous = rendered
                continue
            if not is_shipped_layout(payload) or not rendered:
                previous = rendered
                continue
            assemblies += 1
            estimate = estimate_tokens(carried_turn_files(turn))
            flag = "over" if estimate > args.threshold else "under"
            if estimate > args.threshold:
                over_budget.append(f"{session.name[:28]}/{number:02d}")
            highest = rendered[-1]
            drops = [value for value in previous if value not in rendered and value <= highest]
            previous = rendered
            if not drops:
                continue
            dropped_total += len(drops)
            if estimate > args.threshold:
                dropped_over += len(drops)
            drop_counts[flag] = drop_counts.get(flag, 0) + len(drops)
            if len(detail) < args.show:
                described = ", ".join(
                    f"{value:02d} plan {header_value(paths[value] / 'plan.md', PLAN_STATUS)}"
                    f" report {header_value(paths[value] / 'report.md', REPORT_STATUS)}"
                    for value in drops
                    if value in paths
                )
                detail.append(
                    f"  {session.name[:28]} turn {number:02d}"
                    f" est {estimate:,} tok ({flag}) dropped {drops}"
                )
                detail.append(f"    {described}")

    print("== verdict ==")
    print(f"shipped-layout assemblies {assemblies} | threshold {args.threshold:,} tok")
    print(f"assemblies over budget: {len(over_budget)}")
    print(
        f"turns dropped: {dropped_total}"
        f" | dropped inside an over-budget assembly: {dropped_over}"
    )
    for flag, count in sorted(drop_counts.items()):
        print(f"  dropped during an {flag}-budget assembly: {count}")
    print("\n== assemblers over budget ==")
    for name in over_budget[: args.show] or ["none"]:
        print(f"  {name}")
    print("\n== drop detail ==")
    for line in detail or ["  none"]:
        print(line)


if __name__ == "__main__":
    main()
