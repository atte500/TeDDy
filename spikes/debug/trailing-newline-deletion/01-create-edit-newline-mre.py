"""MRE: EDIT/CREATE actions delete authored trailing newlines.

Parses plans through the production MarkdownPlanParser, writes the resulting
content through the production LocalFileSystemAdapter into a throwaway temp
dir, and prints the exact bytes persisted.

Run from project root:
    uv run python spikes/debug/trailing-newline-deletion/01-create-edit-newline-mre.py
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter,
)
from teddy_executor.core.services.edit_simulator import EditSimulator
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser


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


def main() -> None:
    parser = MarkdownPlanParser()
    tmp = Path(tempfile.mkdtemp(prefix="mre-newline-"))
    adapter = LocalFileSystemAdapter(EditSimulator(), root_dir=str(tmp))

    for name, plan in [("CREATE_PLAIN", CREATE_PLAIN), ("CREATE_BLANK", CREATE_BLANK)]:
        action = parser.parse(plan).actions[0]
        content = action.params["content"]
        path = action.params["path"]
        adapter.create_file(path, content, overwrite=True)
        print(f"[{name}] parsed content  ={content!r}")
        print(f"[{name}] persisted bytes ={(tmp / path).read_bytes()!r}")

    action = parser.parse(EDIT_PLAN).actions[0]
    edit = action.params["edits"][0]
    print(f"[EDIT] parsed find    ={edit['find']!r}")
    print(f"[EDIT] parsed replace ={edit['replace']!r}")

    (tmp / "existing.txt").write_text("old\n", encoding="utf-8", newline="")
    adapter.edit_file("existing.txt", action.params["edits"])
    print(f"[EDIT] persisted bytes ={(tmp / 'existing.txt').read_bytes()!r}")

    print(f"\ntmp dir: {tmp}")


if __name__ == "__main__":
    main()