"""Unit tests for the shared editor-name normalization helper."""

from __future__ import annotations

import os

import pytest

from teddy_executor.core.utils.editor_names import normalize_editor_basename


@pytest.mark.parametrize(
    ("editor_path", "expected"),
    [
        pytest.param("codium.CMD", "codium", id="uppercase-cmd-suffix"),
        pytest.param("nano.BAT", "nano", id="uppercase-bat-suffix"),
        pytest.param("nvim.EXE", "nvim", id="uppercase-exe-suffix"),
        pytest.param("codium.cmd", "codium", id="lowercase-cmd-suffix"),
        pytest.param("Nvim.Cmd", "nvim", id="mixed-case-name-and-suffix"),
        pytest.param("VIM", "vim", id="uppercase-name-without-suffix"),
        pytest.param("code", "code", id="lowercase-name-without-suffix"),
        pytest.param("vim.sh", "vim.sh", id="non-launcher-suffix-preserved"),
        pytest.param("code-insiders", "code-insiders", id="hyphenated-name"),
        pytest.param(
            os.path.join("usr", "local", "bin", "nvim"),
            "nvim",
            id="full-path",
        ),
        pytest.param(
            os.path.join("opt", "VSCodium", "bin", "codium.CMD"),
            "codium",
            id="full-path-with-launcher-suffix",
        ),
        pytest.param("", "", id="empty-path"),
        pytest.param(None, "", id="absent-path"),
    ],
)
def test_normalize_editor_basename(editor_path: str | None, expected: str) -> None:
    assert normalize_editor_basename(editor_path) == expected
