#!/usr/bin/env python3
"""Audit which turns a payload drops and what status each dropped turn carried.

A turn that vanished from the history section must have been deselected for a
reason the code can name, so printing the status of every missing turn either
confirms the failure-pruning mechanism or refutes it. Per turn this reports the
plan's status line, whether the plan is a communicating turn, a hash of its
rationale summary, and the turn numbers its own payload renders.

Two consecutive turns sharing a summary hash means the later plan restated the
earlier one verbatim instead of folding in its outcome, which is the staleness
the summary mechanism cannot rule out on its own.

Section boundaries are fence-aware, so a quoted document cannot invent a section
here, and headers are matched by shape so an embedded document's own subheadings
stay out of the roster. Raw header lines print only behind a flag: a verdict
shares no stream with a dump.

Read-only: it never writes into a session.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

HEADINGS = (
    "Session Resources",
    "Session History",
    "Git Status",
    "Project Structure",
    "Resource Contents",
    "Runtime",
)
STATUS_PREFIX = "- **Status:**"
MESSAGE_MARKER = "\n## Message"
SUMMARY_HEADING = "### Summary"
HISTORY_PREFIX = "### Turn "


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
                if line.rstrip(b"\r\n") == f"## {name}".encode():
                    found.append((offset, name))
        offset += len(line)
    return found


def section(payload: bytes, name: str) -> bytes:
    """One section's bytes, bounded by the next real heading."""
    located = marks(payload)
    for index, (offset, found_name) in enumerate(located):
        if found_name != name:
            continue
        end = located[index + 1][0] if index + 1 < len(located) else len(payload)
        return payload[offset:end]
    return b""


def history_headers(payload: bytes) -> list[str]:
    """The rendered history header lines, in document order."""
    body = section(payload, "Session History").decode("utf-8", "replace")
    return [line for line in body.splitlines() if line.startswith(HISTORY_PREFIX)]


def rendered_turns(payload: bytes) -> list[int]:
    """The turn numbers whose plan or report the payload renders."""
    numbers: set[int] = set()
    for line in history_headers(payload):
        label = line[len(HISTORY_PREFIX) :]
        number = label.split(":", 1)[0].strip()
        if number.isdigit():
            numbers.add(int(number))
    return sorted(numbers)


def block(text: str, heading: str) -> str:
    """The body between one level-three heading and the next one."""
    start = text.find(heading)
    if start < 0:
        return ""
    start += len(heading)
    end = text.find("\n### ", start)
    return text[start : end if end >= 0 else len(text)].strip()


def plan_facts(plan_path: Path) -> dict:
    """A plan's status line, message flag, and summary fingerprint."""
    if not plan_path.exists():
        return {"status": "(no plan.md)", "message": None, "summary": ""}
    plan = plan_path.read_text(encoding="utf-8")
    status = "(no status line)"
    for line in plan.splitlines():
        if line.startswith(STATUS_PREFIX):
            status = line[len(STATUS_PREFIX) :].strip()
            break
    summary = block(plan, SUMMARY_HEADING)
    digest = hashlib.sha256(summary.encode("utf-8")).hexdigest()[:8] if summary else ""
    return {
        "status": status,
        "message": MESSAGE_MARKER in plan,
        "summary": digest,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True, help="path to a session dir")
    parser.add_argument("--first", type=int, default=1)
    parser.add_argument("--last", type=int, default=999)
    parser.add_argument("--headers", action="store_true", help="dump raw header lines")
    args = parser.parse_args()

    session = Path(args.session)
    turns = sorted(
        (child for child in session.iterdir() if child.is_dir() and child.name.isdigit()),
        key=lambda child: int(child.name),
    )
    facts = {int(turn.name): plan_facts(turn / "plan.md") for turn in turns}
    hole_causes: dict[str, int] = {}
    identical: list[str] = []
    previous: tuple[int, str] | None = None

    for turn in turns:
        number = int(turn.name)
        if not (args.first <= number <= args.last):
            continue
        fact = facts[number]
        payload_path = turn / "input.md"
        label = "plan" if fact["message"] is not None else "none"
        print(
            f"\nturn {number:02d} status {fact['status']}"
            f" | message={label} | summary={fact['summary'] or 'none'}"
        )
        if fact["summary"]:
            if previous and previous[1] == fact["summary"]:
                identical.append(f"{previous[0]:02d}->{number:02d}")
                print(f"  summary identical to turn {previous[0]:02d}")
            previous = (number, fact["summary"])
        if not payload_path.exists():
            print("  no payload")
            continue
        payload = payload_path.read_bytes()
        roster = rendered_turns(payload)
        print(f"  renders {roster} ({len(payload):,} B)")
        if roster:
            window = range(1, roster[-1] + 1)
            missing = [value for value in window if value not in roster]
            if missing:
                described = ", ".join(
                    f"{value:02d} {facts.get(value, {}).get('status', 'absent')}"
                    for value in missing
                )
                print(f"  missing {described}")
                for value in missing:
                    cause = facts.get(value, {}).get("status", "absent")
                    hole_causes[cause] = hole_causes.get(cause, 0) + 1
        if args.headers:
            for line in history_headers(payload):
                print(f"    {line}")

    print("\n== verdict ==")
    if hole_causes:
        census = ", ".join(
            f"{name} {count}" for name, count in sorted(hole_causes.items())
        )
        print(f"dropped turns by status: {census}")
    else:
        print("dropped turns by status: none")
    print(f"turns restating the previous summary verbatim: {identical or 'none'}")


if __name__ == "__main__":
    main()
