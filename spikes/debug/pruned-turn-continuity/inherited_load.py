#!/usr/bin/env python3
"""Estimate the full turn-scope load an assembly inherited before pruning.

The budget fires on the sum of every selected Turn-scope item, and a turn-scope
item is any project file the turn gathered: a READ of a large document lands in
turn.context and counts against the threshold. An estimate that keeps only
NN/plan.md and NN/report.md therefore understates the load precisely when a turn
spent its budget reading, which is what made an earlier probe report almost no
over-budget assemblies.

Two corrections separate this from that probe:

* Turn N is assembled from the manifest turn N-1 left behind, so that is the
  manifest read here, never turn N's own.
* Session-scope paths are exempt from the budget, so they are read from
  session.context and subtracted.

Pruning also only ever removes a file, so the estimate counts paths that still
exist; a path deleted from disk was pruned for another reason already.

The estimate is characters over four, so an absolute figure is approximate. An
assembly far above or far below 50,000 stays decisive, and the verdict is stated
as a split between the two rather than as a precise count.

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
    found: set[int] = set()
    for line in outside_fence_lines(history_body(payload_path.read_bytes())):
        match = HISTORY_LINE.match(line)
        if match:
            found.add(int(match.group(1)))
    return sorted(found)


def is_shipped_layout(payload: bytes) -> bool:
    """Whether the payload carries the constant header and a runtime tail."""
    return payload.startswith(b"# Project Context\n") and b"\n## Runtime\n" in payload


def normalized(entry: str) -> str:
    """One manifest line as a forward-slash path without surrounding space."""
    return entry.strip().replace("\\", "/")


def session_paths(session: Path) -> set[str]:
    """The prune-exempt session manifest, which the budget never counts."""
    manifest = session / "session.context"
    if not manifest.exists():
        return set()
    return {
        normalized(line)
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }


def inherited_files(turn_dir: Path, exempt: set[str]) -> list[Path]:
    """Every existing non-session file the turn's manifest listed."""
    manifest = turn_dir / "turn.context"
    if not manifest.exists():
        return []
    found: dict[str, Path] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        entry = normalized(line)
        if not entry or entry.startswith("#") or entry in exempt:
            continue
        if entry.endswith(".context"):
            continue
        candidate = Path(entry)
        if candidate.is_file():
            found[entry] = candidate
    return list(found.values())


def estimate_tokens(files: list[Path]) -> int:
    """The characters-over-four estimate over the inherited files."""
    total = 0
    for path in files:
        try:
            total += len(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
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
    parser.add_argument("--show", type=int, default=14, help="detail lines to print")
    args = parser.parse_args()

    assemblies = 0
    over: list[str] = []
    front_pairs = 0
    mid_total = 0
    mid_over = 0
    mid_under = 0
    mid_by_status: dict[str, int] = {}
    detail: list[str] = []

    for session in sorted(Path(args.sessions_dir).iterdir()):
        if not session.is_dir():
            continue
        turns = sorted(
            (child for child in session.iterdir() if child.is_dir() and child.name.isdigit()),
            key=lambda child: int(child.name),
        )
        paths = {int(turn.name): turn for turn in turns}
        exempt = session_paths(session)
        for index, number in enumerate(sorted(paths)):
            current = paths[number]
            payload_path = current / "input.md"
            if not payload_path.exists() or index == 0:
                continue
            previous_number = sorted(paths)[index - 1]
            if not (paths[previous_number] / "input.md").exists():
                continue
            payload = payload_path.read_bytes()
            if not is_shipped_layout(payload):
                continue
            after = rendered_ids(payload_path)
            before = rendered_ids(paths[previous_number] / "input.md")
            if not before or not after:
                continue
            assemblies += 1
            estimate = estimate_tokens(inherited_files(paths[previous_number], exempt))
            flag = "over" if estimate > args.threshold else "under"
            if estimate > args.threshold:
                over.append(f"{session.name[:26]}/{number:02d} {estimate:,}tok")
            if min(before) != min(after):
                front_pairs += 1
            holes = [
                value for value in before if value not in after and min(after) < value
            ]
            if not holes:
                continue
            mid_total += len(holes)
            if estimate > args.threshold:
                mid_over += len(holes)
            else:
                mid_under += len(holes)
            for value in holes:
                key = (
                    f"{header_value(paths[value] / 'plan.md', PLAN_STATUS)}"
                    f" report {header_value(paths[value] / 'report.md', REPORT_STATUS)}"
                )
                mid_by_status[key] = mid_by_status.get(key, 0) + 1
            if len(detail) < args.show:
                detail.append(
                    f"  {session.name[:26]} turn {number:02d}"
                    f" est {estimate:,} tok ({flag}) holes {holes}"
                )

    print("== verdict ==")
    print(f"shipped-layout assemblies {assemblies} | threshold {args.threshold:,} tok")
    print(f"assemblies over budget: {len(over)} ({len(over) / assemblies:.1%})" if assemblies else "none")
    print(f"pairs whose oldest rendered turn moved (front truncation): {front_pairs}")
    print(
        f"turns removed mid-history: {mid_total}"
        f" | inside over-budget: {mid_over} | inside under-budget: {mid_under}"
    )
    print("\n== mid-history removals, by the turn's own status ==")
    for name, count in sorted(mid_by_status.items(), key=lambda item: -item[1]):
        print(f"  {count:>4}  {name}")
    print("\n== assemblies over budget ==")
    for name in over[: args.show] or ["none"]:
        print(f"  {name}")
    print("\n== hole detail ==")
    for line in detail or ["  none"]:
        print(line)


if __name__ == "__main__":
    main()
