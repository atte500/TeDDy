"""Newline-determinism contract for LocalFileSystemAdapter.write_file.

Internal TeDDy persistence (session ledger, plans, prompts, reports) flows
through write_file, which MUST be newline-deterministic: the in-memory string
is emitted to disk verbatim (LF line endings) on every platform, so
byte-exact persistence contracts (session migration, hashing, diffing) hold
identically on POSIX and Windows.
"""

from pathlib import Path

from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter,
)
from teddy_executor.core.services.edit_simulator import EditSimulator


def _make_adapter(tmp_path: Path) -> LocalFileSystemAdapter:
    return LocalFileSystemAdapter(
        edit_simulator=EditSimulator(),
        root_dir=str(tmp_path),
    )


def test_write_file_emits_lf_verbatim_bytes(tmp_path):
    """write_file persists content with LF line endings on every platform."""
    adapter = _make_adapter(tmp_path)

    adapter.write_file("ledger.context", "README.md\n")

    assert (tmp_path / "ledger.context").read_bytes() == b"README.md\n"


def test_write_file_multiline_content_has_no_platform_translation(tmp_path):
    """Every embedded newline in multi-line content is written as LF verbatim."""
    adapter = _make_adapter(tmp_path)
    content = "line1\nline2\nline3\n"

    adapter.write_file("multi.context", content)

    assert (tmp_path / "multi.context").read_bytes() == b"line1\nline2\nline3\n"
