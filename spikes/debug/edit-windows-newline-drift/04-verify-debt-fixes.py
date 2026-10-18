"""Proof: the parser and CREATE newline debt fixes hold byte-exactly.

Case 1 compares the production plan parser with the replica over a CRLF
clipboard plan. The production parser leaves trailing carriage returns on
the FIND and REPLACE blocks. The replica normalizes plan line endings to LF
before parsing, so both blocks are clean.

Case 2 compares the production adapter with the replica under an emulated
Windows ``open`` translation. The production ``create_file`` emits CRLF
bytes. The replica passes ``newline=""`` and emits the content verbatim.
"""

from __future__ import annotations

import builtins
import importlib.util
import sys
import tempfile
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter as ProductionAdapter,
)
from teddy_executor.core.services.edit_simulator import EditSimulator
from teddy_executor.core.services.markdown_plan_parser import (
    MarkdownPlanParser as ProductionPlanParser,
)

CRLF = "\r\n"
_REAL_OPEN = builtins.open


def _load_replica(module_name: str, file_name: str):
    path = Path(__file__).with_name(file_name)
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ReplicaPlanParser = _load_replica(
    "replica_plan_parser", "replica_markdown_plan_parser.py"
).MarkdownPlanParser
ReplicaAdapter = _load_replica(
    "replica_adapter_debts", "replica_local_file_system_adapter.py"
).LocalFileSystemAdapter


def _emulate_windows_open(
    file,
    mode="r",
    buffering=-1,
    encoding=None,
    errors=None,
    newline=None,
    closefd=True,
    opener=None,
):
    """Translate default-newline text writes to CRLF to emulate Windows."""
    is_text_write = "b" not in mode and any(flag in mode for flag in "wax")
    effective_newline = CRLF if newline is None and is_text_write else newline
    return _REAL_OPEN(
        file, mode, buffering, encoding, errors, effective_newline, closefd, opener
    )


def _crlf_plan() -> str:
    lf_plan = (
        MarkdownPlanBuilder("Windows Clipboard Plan")
        .add_edit("sample.txt", "second line", "replacement one\nreplacement two")
        .build()
    )
    return lf_plan.replace("\n", CRLF)


def _first_edit(parser) -> dict[str, str]:
    plan = parser.parse(_crlf_plan())
    return plan.actions[0].params["edits"][0]


def _check_plan_parser() -> bool:
    production_edit = _first_edit(ProductionPlanParser())
    replica_edit = _first_edit(ReplicaPlanParser())

    print("Case 1: CRLF plan through the parser")
    print(f"  production find:    {production_edit['find']!r}")
    print(f"  production replace: {production_edit['replace']!r}")
    print(f"  replica find:       {replica_edit['find']!r}")
    print(f"  replica replace:    {replica_edit['replace']!r}")

    clean = "\r" not in replica_edit["find"] and "\r" not in replica_edit["replace"]
    print(f"  replica blocks carry no carriage return: {clean}")
    return clean


def _create_file_bytes(adapter_class) -> bytes:
    builtins.open = _emulate_windows_open
    try:
        with tempfile.TemporaryDirectory() as root:
            adapter = adapter_class(edit_simulator=EditSimulator(), root_dir=root)
            adapter.create_file("created.txt", "line one\nline two\n")
            return (Path(root) / "created.txt").read_bytes()
    finally:
        builtins.open = _REAL_OPEN


def _check_create_file() -> bool:
    expected = b"line one\nline two\n"
    production_bytes = _create_file_bytes(ProductionAdapter)
    replica_bytes = _create_file_bytes(ReplicaAdapter)

    print("Case 2: create_file under emulated Windows write")
    print(f"  expected bytes:   {expected!r}")
    print(f"  production bytes: {production_bytes!r}")
    print(f"  replica bytes:    {replica_bytes!r}")

    byte_exact = replica_bytes == expected
    print(f"  replica byte exact: {byte_exact}")
    return byte_exact


def main() -> int:
    results = [_check_plan_parser(), _check_create_file()]
    print("DEBT FIXES PROVEN" if all(results) else "DEBT FIXES NOT PROVEN")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())