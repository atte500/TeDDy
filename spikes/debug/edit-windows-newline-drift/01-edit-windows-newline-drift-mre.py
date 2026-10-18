"""MRE: EDIT actions double line endings on Windows.

Windows ``Path.write_text`` defaults to ``newline=None``, so every "\n" is
translated to ``os.linesep`` ("\r\n"). When an EDIT replacement already
carries CRLF, the file receives CRLFCRLF, which universal-newline readers
render as an extra blank line. This script emulates that Windows write
translation on any host.
"""

from __future__ import annotations

import pathlib
import tempfile
from pathlib import Path

_ORIGINAL_WRITE_TEXT = pathlib.Path.write_text


def _emulate_windows_write_text(self, data, encoding=None, errors=None, newline=None):
    if newline is None:
        data = data.replace("\n", "\r\n")
    return _ORIGINAL_WRITE_TEXT(
        self, data, encoding=encoding, errors=errors, newline=newline
    )


def _edit_under_emulated_windows(
    initial_bytes: bytes, edits: list[dict[str, str]]
) -> bytes:
    from teddy_executor.adapters.outbound.local_file_system_adapter import (
        LocalFileSystemAdapter,
    )
    from teddy_executor.core.services.edit_simulator import EditSimulator

    pathlib.Path.write_text = _emulate_windows_write_text
    try:
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "target.txt"
            target.write_bytes(initial_bytes)
            adapter = LocalFileSystemAdapter(
                edit_simulator=EditSimulator(), root_dir=root
            )
            adapter.edit_file("target.txt", edits=edits)
            return target.read_bytes()
    finally:
        pathlib.Path.write_text = _ORIGINAL_WRITE_TEXT


def main() -> int:
    plain_expected = b"line one\nline 2\n"
    plain_actual = _edit_under_emulated_windows(
        b"line one\nline two\n",
        [{"find": "line two", "replace": "line 2"}],
    )

    crlf_expected = b"start\nx\r\ny\n"
    crlf_actual = _edit_under_emulated_windows(
        b"start\nend\n",
        [{"find": "end", "replace": "x\r\ny"}],
    )

    print("Case 1: plain LF replacement")
    print(f"  expected bytes: {plain_expected!r}")
    print(f"  actual bytes:   {plain_actual!r}")

    print("Case 2: CRLF inside replacement")
    print(f"  expected bytes: {crlf_expected!r}")
    print(f"  actual bytes:   {crlf_actual!r}")
    print(f"  rendered lines: {crlf_actual.decode(chr(117) + 'tf-8').splitlines()}")

    drift = plain_actual != plain_expected
    doubled = b"\r\r\n" in crlf_actual
    print(f"plain newline drift: {drift}")
    print(f"doubled CRLF: {doubled}")

    reproduced = drift or doubled
    print("BUG REPRODUCED" if reproduced else "BUG NOT REPRODUCED")
    return 1 if reproduced else 0


if __name__ == "__main__":
    raise SystemExit(main())