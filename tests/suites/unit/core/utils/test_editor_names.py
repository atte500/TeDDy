"""Unit tests for the shared editor-name normalization helper."""

from __future__ import annotations

import os

import pytest

from teddy_executor.core.utils.editor_names import (
    CLI_EDITORS,
    is_cli_editor,
    normalize_editor_basename,
)


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


@pytest.mark.parametrize(
    "editor_cmd",
    [
        pytest.param(["vim"], id="vim"),
        pytest.param(["nvim", "--clean"], id="nvim-with-args"),
        pytest.param(["vi"], id="vi"),
        pytest.param(["nano"], id="nano"),
        pytest.param(["micro"], id="micro"),
        pytest.param(["emacs", "-nw"], id="emacs"),
        pytest.param(["pico"], id="pico"),
        pytest.param(["helix"], id="helix"),
        pytest.param(["hx"], id="hx"),
        pytest.param(["kak"], id="kak"),
        pytest.param(["/usr/local/bin/nvim"], id="full-path"),
        pytest.param(["nvim.CMD"], id="uppercase-cmd-wrapper"),
        pytest.param(["nvim.exe"], id="lowercase-exe-wrapper"),
        pytest.param(["nano.BAT"], id="uppercase-bat-wrapper"),
        pytest.param(["Nvim.Cmd"], id="mixed-case-wrapper"),
    ],
)
def test_is_cli_editor_true_for_terminal_editors(editor_cmd: list[str]) -> None:
    assert is_cli_editor(editor_cmd) is True


@pytest.mark.parametrize(
    "editor_cmd",
    [
        pytest.param(["code"], id="code"),
        pytest.param(["code", "--wait", "."], id="code-with-args"),
        pytest.param(["cursor"], id="cursor"),
        pytest.param(["subl"], id="subl"),
        pytest.param(["codium.CMD"], id="codium-cmd-wrapper"),
        pytest.param(["code.EXE"], id="code-exe-wrapper"),
        pytest.param(["/opt/bin/my_editor"], id="unknown-full-path"),
        pytest.param([], id="empty-command"),
        pytest.param(None, id="absent-command"),
    ],
)
def test_is_cli_editor_false_for_gui_or_unknown(
    editor_cmd: list[str] | None,
) -> None:
    assert is_cli_editor(editor_cmd) is False


def test_cli_editors_set_is_single_source() -> None:
    """The shared set pins the terminal-editor names used by the classifier."""
    expected = {
        "vim",
        "nvim",
        "vi",
        "nano",
        "micro",
        "emacs",
        "pico",
        "helix",
        "hx",
        "kak",
    }
    assert set(CLI_EDITORS) == expected
