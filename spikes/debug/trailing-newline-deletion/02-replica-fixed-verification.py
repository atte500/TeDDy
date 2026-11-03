"""Verify the fix: replica strategy functions preserve authored trailing newlines.

Runs identical plans through:
  (a) the PRODUCTION MarkdownPlanParser (buggy: strips trailing newlines), and
  (b) a MarkdownPlanParser whose CREATE/EDIT dispatch is wired to the fixed
      replica strategies,
both writing through the real LocalFileSystemAdapter into throwaway temp dirs.

Run from project root:
    uv run python spikes/debug/trailing-newline-deletion/02-replica-fixed-verification.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter,
)
from teddy_executor.core.services.edit_simulator import EditSimulator
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser

from replica_action_parser_complex import parse_edit_action as fixed_edit
from replica_action_parser_strategies import parse_create_action as fixed_create


def wrap(action_block: str) -> str:
    return (
        "# Probe Plan\n"
        "- **Agent:** Debugger\n"
        "- **Plan Type:** Investigation\n"
        "- **Status:** ON-TRACK\n"
        "\n"
        "## Rationale\n"
        "~~~~~~\n"
        "probe\n"
        "~~~~~~\n"
        "\n"
        "## Action Plan\n"
        "\n"
        f"{action_block}\n"
    )


CREATE_PLAIN = wrap(
    "### `CREATE`\n"
    "- **File Path:** `plain.txt`\n"
    "- **Description:** plain\n"
    "~~~~~~\n"
    "line1\n"
    "line2\n"
    "~~~~~~"
)

CREATE_BLANK = wrap(
    "### `CREATE`\n"
    "- **File Path:** `blank.txt`\n"
    "- **Description:** blank\n"
    "~~~~~~\n"
    "line1\n"
    "line2\n"
    "\n"
    "~~~~~~"
)

EDIT_PLAN = wrap(
    "### `EDIT`\n"
    "- **File Path:** `existing.txt`\n"
    "- **Description:** edit\n"
    "\n"
    "#### `FIND:`\n"
    "~~~~~~\n"
    "old\n"
    "~~~~~~\n"
    "\n"
    "#### `REPLACE:`\n"
    "~~~~~~\n"
    "new\n"
    "\n"
    "~~~~~~"
)


def make_parser(fixed: bool) -> MarkdownPlanParser:
    parser = MarkdownPlanParser()
    if fixed:
        parser._dispatch_map["CREATE"] = fixed_create
        parser._dispatch_map["EDIT"] = lambda s, node=None: fixed_edit(
            s, parser._valid_actions, node=node
        )
    return parser


def create_bytes(parser, plan: str) -> tuple[str, bytes]:
    action = parser.parse(plan).actions[0]
    tmp = Path(tempfile.mkdtemp(prefix="verify-"))
    adapter = LocalFileSystemAdapter(EditSimulator(), root_dir=str(tmp))
    adapter.create_file(action.params["path"], action.params["content"], overwrite=True)
    return action.params["content"], (tmp / action.params["path"]).read_bytes()


def edit_bytes(parser, plan: str) -> tuple[dict, bytes]:
    action = parser.parse(plan).actions[0]
    edit = action.params["edits"][0]
    tmp = Path(tempfile.mkdtemp(prefix="verify-"))
    (tmp / "existing.txt").write_text("old\n", encoding="utf-8", newline="")
    adapter = LocalFileSystemAdapter(EditSimulator(), root_dir=str(tmp))
    adapter.edit_file("existing.txt", action.params["edits"])
    return edit, (tmp / "existing.txt").read_bytes()


def main() -> None:
    prod = make_parser(fixed=False)
    fix = make_parser(fixed=True)

    print("== CREATE_PLAIN ==")
    pc, pb = create_bytes(prod, CREATE_PLAIN)
    fc, fb = create_bytes(fix, CREATE_PLAIN)
    print(f"prod content={pc!r} bytes={pb!r}")
    print(f"fix  content={fc!r} bytes={fb!r}")
    assert pb == b"line1\nline2", f"prod should strip trailing newline: {pb!r}"
    assert fb == b"line1\nline2\n", f"fix should preserve trailing newline: {fb!r}"

    print("== CREATE_BLANK ==")
    pc, pb = create_bytes(prod, CREATE_BLANK)
    fc, fb = create_bytes(fix, CREATE_BLANK)
    print(f"prod content={pc!r} bytes={pb!r}")
    print(f"fix  content={fc!r} bytes={fb!r}")
    assert pb == b"line1\nline2", f"prod should strip authored blank line: {pb!r}"
    assert fb == b"line1\nline2\n\n", f"fix should preserve authored blank line: {fb!r}"

    print("== EDIT (REPLACE with authored trailing blank line) ==")
    pe, pb = edit_bytes(prod, EDIT_PLAN)
    fe, fb = edit_bytes(fix, EDIT_PLAN)
    print(f"prod find={pe['find']!r} replace={pe['replace']!r} bytes={pb!r}")
    print(f"fix  find={fe['find']!r} replace={fe['replace']!r} bytes={fb!r}")
    assert pe["find"] == "old" and pe["replace"] == "new", f"prod should strip: {pe!r}"
    assert fe["find"] == "old\n" and fe["replace"] == "new\n\n", (
        f"fix should preserve newlines: {fe!r}"
    )
    assert pb != b"new\n\n", f"prod lost the authored blank line: {pb!r}"
    assert fb == b"new\n\n", f"fix should persist authored blank line: {fb!r}"

    print("\nPASS: replica fix preserves authored trailing newlines end-to-end.")


if __name__ == "__main__":
    main()