"""Proof: the verbatim-write fix removes the Windows line-ending drift.

The replica is a copy of the production adapter whose edit_file writes with
``newline=""``. This script drives the replica under emulated Windows write
semantics and asserts byte-exact results. The final case pushes a CRLF
clipboard plan through the real parser and simulator to prove the full
chain.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import tempfile
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_REPLICA_PATH = Path(__file__).with_name("replica_local_file_system_adapter.py")
_spec = importlib.util.spec_from_file_location("replica_adapter", _REPLICA_PATH)
assert _spec is not None and _spec.loader is not None
_replica = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_replica)
ReplicaFileSystemAdapter = _replica.LocalFileSystemAdapter

from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from teddy_executor.core.services.edit_simulator import EditSimulator
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser

CRLF = "\r\n"
_ORIGINAL_WRITE_TEXT = pathlib.Path.write_text


def _emulate_windows_write_text(self, data, encoding=None, errors=None, newline=None):
    if newline is None:
        data = data.replace("\n", CRLF)
    return _ORIGINAL_WRITE_TEXT(
        self, data, encoding=encoding, errors=errors, newline=newline
    )


def _edit(initial_bytes: bytes, edits: list[dict[str, str]]) -> bytes:
    with tempfile.TemporaryDirectory() as root:
        target = Path(root) / "target.txt"
        target.write_bytes(initial_bytes)
        adapter = ReplicaFileSystemAdapter(
            edit_simulator=EditSimulator(), root_dir=root
        )
        adapter.edit_file("target.txt", edits=edits)
        return target.read_bytes()


def _clipboard_edits() -> list[dict[str, str]]:
    lf_plan = (
        MarkdownPlanBuilder("Windows Clipboard Plan")
        .add_edit("target.txt", "second line", "replacement one\nreplacement two")
        .build()
    )
    plan = MarkdownPlanParser().parse(lf_plan.replace("\n", CRLF))
    return plan.actions[0].params["edits"]


def main() -> int:
    cases = [
        (
            "plain LF replacement",
            b"line one\nline two\n",
            [{"find": "line two", "replace": "line 2"}],
            b"line one\nline 2\n",
        ),
        (
            "CRLF inside replacement",
            b"start\nend\n",
            [{"find": "end", "replace": "x\r\ny"}],
            b"start\nx\r\ny\n",
        ),
        (
            "CRLF clipboard plan end to end",
            b"first line\nsecond line\nlast line\n",
            _clipboard_edits(),
            b"first line\nreplacement one\r\nreplacement two\r\nlast line\n",
        ),
    ]

    failures = 0
    pathlib.Path.write_text = _emulate_windows_write_text
    try:
        for name, initial, edits, expected in cases:
            actual = _edit(initial, edits)
            ok = actual == expected
            print(f"{name}: {'PASS' if ok else 'FAIL'}")
            print(f"  expected bytes: {expected!r}")
            print(f"  actual bytes:   {actual!r}")
            if not ok:
                failures += 1
    finally:
        pathlib.Path.write_text = _ORIGINAL_WRITE_TEXT

    print("FIX PROVEN" if failures == 0 else "FIX NOT PROVEN")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())