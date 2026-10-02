"""Regression tests for Bug 56 (deliverable 2): the console ask loop's
CLI-editor branch must restore the terminal cooked mode after the synchronous
editor exits.

The ask loop launches a CLI editor (vim/nvim) via a direct ``subprocess.run``
-- bypassing ``ISystemEnvironment.run_command`` and its emergency TTY restore
-- so it forfeits any terminal-mode repair after the editor exits in raw mode.
Mirroring ``ConsoleInteractorAdapter._launch_editor_synchronous`` (which calls
``restore_terminal_mode()`` after ``run_command``), the ask loop must invoke
the shared ``restore_terminal_mode`` helper so the terminal keeps GENERATING
SIGINT for later Ctrl+C interrupts.

The GUI/background editor path must remain unchanged (no restore).
"""

import subprocess

import pytest

import teddy_executor.adapters.outbound.console_interactor_ask_loop as ask_loop_module
from teddy_executor.adapters.outbound.console_interactor_ask_loop import (
    ConsoleAskLoop,
)


class _TempFileSystemEnv:
    """Minimal in-memory ISystemEnvironment fake for the ask-loop editor path."""

    def __init__(self, temp_path):
        self._temp_path = str(temp_path)
        self.deleted = []

    def create_temp_file(self, suffix="", mode="w"):
        return self._temp_path

    def delete_file(self, path):
        self.deleted.append(path)


class _EditorTooling:
    """Minimal tooling fake that returns a fixed editor command."""

    def __init__(self, editor_cmd):
        self._editor_cmd = editor_cmd

    def find_editor(self):
        return self._editor_cmd


class _CallRecorder:
    """Hand-rolled call recorder (not a mock) appending a label per call."""

    def __init__(self, events, label):
        self._events = events
        self._label = label

    def __call__(self, *args, **kwargs):
        self._events.append(self._label)


@pytest.fixture
def events():
    return []


def test_cli_editor_restores_terminal_after_editor_exit(tmp_path, events, monkeypatch):
    """A CLI-editor launch must restore the terminal cooked mode after exit."""
    loop = ConsoleAskLoop(
        _TempFileSystemEnv(tmp_path / "editor.md"),
        _EditorTooling(["/usr/bin/vim"]),
    )
    monkeypatch.setattr(subprocess, "run", _CallRecorder(events, "run"))
    monkeypatch.setattr(
        ask_loop_module,
        "restore_terminal_mode",
        _CallRecorder(events, "restore"),
        raising=False,
    )

    loop._launch_editor_background("test prompt")

    assert "restore" in events, (
        "the CLI-editor branch must restore the terminal cooked mode after the "
        "editor exits (mirroring ConsoleInteractor._launch_editor_synchronous)"
    )
    assert events.index("restore") > events.index("run"), (
        "the terminal restore must run AFTER the editor subprocess exits"
    )


def test_gui_editor_path_does_not_restore_terminal(tmp_path, events, monkeypatch):
    """The GUI/background editor path must remain unchanged (no restore)."""
    loop = ConsoleAskLoop(
        _TempFileSystemEnv(tmp_path / "editor.md"),
        _EditorTooling(["code"]),
    )
    monkeypatch.setattr(subprocess, "Popen", _CallRecorder(events, "popen"))
    monkeypatch.setattr(
        ask_loop_module,
        "restore_terminal_mode",
        _CallRecorder(events, "restore"),
        raising=False,
    )

    loop._launch_editor_background("test prompt")

    assert "popen" in events, "the GUI editor must be launched via Popen"
    assert "restore" not in events, (
        "the GUI/background editor path must not restore the terminal"
    )
