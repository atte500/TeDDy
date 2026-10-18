"""Probe: trace CRLF from a clipboard plan to the bytes written to disk.

A plan pasted from the Windows clipboard carries CRLF line endings. This
probe records whether those endings survive the Markdown parser, what the
simulator produces in memory, and which bytes the adapter writes when the
platform translates newlines on write.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from teddy_executor.core.services.edit_simulator import EditSimulator

CRLF = "\r\n"


def _build_clipboard_plan() -> str:
    lf_plan = (
        MarkdownPlanBuilder("Windows Clipboard Plan")
        .add_edit("sample.txt", "second line", "replacement one\nreplacement two")
        .build()
    )
    return lf_plan.replace("\n", CRLF)


def main() -> int:
    from teddy_executor.adapters.outbound.local_file_system_adapter import (
        LocalFileSystemAdapter,
    )
    from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser

    plan_text = _build_clipboard_plan()
    plan = MarkdownPlanParser().parse(plan_text)
    edits = plan.actions[0].params["edits"]
    edit = edits[0]

    print(f"plan carries CRLF: {CRLF in plan_text}")
    print(f"parsed find:    {edit['find']!r}")
    print(f"parsed replace: {edit['replace']!r}")
    parser_keeps_crlf = "\r" in edit["replace"]
    print(f"parser keeps CRLF in replacement: {parser_keeps_crlf}")

    in_memory, _ = EditSimulator().simulate_edits(
        "first line\nsecond line\nlast line\n",
        [{"find": edit["find"], "replace": edit["replace"]}],
    )
    print(f"simulated content: {in_memory!r}")

    original_write_text = pathlib.Path.write_text

    def emulate_windows_write_text(self, data, encoding=None, errors=None, newline=None):
        if newline is None:
            data = data.replace("\n", CRLF)
        return original_write_text(
            self, data, encoding=encoding, errors=errors, newline=newline
        )

    final_bytes = b""
    pathlib.Path.write_text = emulate_windows_write_text
    try:
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "sample.txt"
            target.write_bytes(b"first line\nsecond line\nlast line\n")
            adapter = LocalFileSystemAdapter(
                edit_simulator=EditSimulator(), root_dir=root
            )
            adapter.edit_file("sample.txt", edits=edits)
            final_bytes = target.read_bytes()
    finally:
        pathlib.Path.write_text = original_write_text

    print(f"final bytes: {final_bytes!r}")
    print(f"final bytes contain CRLFCRLF: {b'\r\r\n' in final_bytes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())