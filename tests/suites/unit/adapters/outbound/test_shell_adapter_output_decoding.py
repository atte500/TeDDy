"""Regression tests: ShellAdapter stream decoding for captured child output.

The adapter drains child pipes in bytes mode and decodes each stream
explicitly. A byte that is invalid in the host locale codec therefore can
never kill a pipe-reader thread and silently drop the payload.
"""

import sys

from teddy_executor.adapters.outbound.shell_adapter import ShellAdapter


def test_decode_stream_passes_text_through():
    adapter = ShellAdapter()
    assert adapter._decode_stream("plain text") == "plain text"


def test_decode_stream_returns_empty_string_for_none():
    adapter = ShellAdapter()
    assert adapter._decode_stream(None) == ""


def test_decode_stream_decodes_utf8_bytes():
    adapter = ShellAdapter()
    assert adapter._decode_stream("\u2705 ok".encode("utf-8")) == "\u2705 ok"


def test_decode_stream_replaces_undecodable_bytes():
    adapter = ShellAdapter()
    assert adapter._decode_stream(bytes([0x90])) == "\ufffd"


def test_decode_stream_normalizes_windows_newlines():
    adapter = ShellAdapter()
    assert adapter._decode_stream(b"a\r\nb\rc") == "a\nb\nc"


def test_spawn_kwargs_request_bytes_mode():
    adapter = ShellAdapter()
    kwargs = adapter._prepare_subprocess_kwargs(use_shell=False, cwd=".", env={})
    assert "text" not in kwargs
    assert "encoding" not in kwargs


def test_execute_preserves_output_when_child_emits_undecodable_byte(tmp_path):
    helper = tmp_path / "emit_invalid_byte.py"
    helper.write_text(
        "import sys\nsys.stdout.buffer.write(bytes([144, 10]))\n",
        encoding="utf-8",
    )
    adapter = ShellAdapter()

    result = adapter.execute(f'"{sys.executable}" "{helper}"', cwd=str(tmp_path))

    assert result["return_code"] == 0
    assert result["stdout"] is not None
    assert "\ufffd" in result["stdout"]
