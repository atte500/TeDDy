from unittest.mock import patch
from teddy_executor.adapters.outbound.shell_command_builder import ShellCommandBuilder


def test_builder_prepares_simple_command_without_shell():
    builder = ShellCommandBuilder(platform="linux")
    cmd, use_shell = builder.prepare("ls -la")
    assert cmd == "ls -la"
    assert use_shell is True


def test_builder_prepares_complex_posix_command_with_bash_trap():
    builder = ShellCommandBuilder(platform="linux")
    with patch("shutil.which", return_value="/bin/bash"):
        cmd, use_shell = builder.prepare("echo hello && exit 1")

    assert isinstance(cmd, list)
    assert cmd[0] == "bash"
    assert "trap 'TEDDY_LAST_CMD=$BASH_COMMAND' DEBUG" in cmd[2]
    assert "echo hello && exit 1" in cmd[2]
    assert use_shell is False


def test_builder_prepares_multiline_windows_command_with_wrapping():
    builder = ShellCommandBuilder(platform="win32")
    # Multiline commands on Windows should be wrapped line-by-line
    cmd, use_shell = builder.prepare("dir\necho done")

    assert "(call dir || cmd /c" in cmd
    assert "(call echo done || cmd /c" in cmd
    assert use_shell is True


def test_builder_prepares_single_line_chain_windows_command_with_wrapping():
    builder = ShellCommandBuilder(platform="win32")
    # Single line chains are wrapped as a single unit
    cmd, use_shell = builder.prepare("dir && echo done")

    assert (
        '(call dir && echo done || cmd /c "echo FAILED_COMMAND: dir ^&^& echo done'
        in cmd
    )
    assert use_shell is True


def test_builder_identifies_executable_on_windows():
    builder = ShellCommandBuilder(platform="win32")
    with patch("shutil.which", return_value="C:\\Windows\\System32\\notepad.exe"):
        cmd, use_shell = builder.prepare("notepad.exe")
    assert cmd == "notepad.exe"
    assert use_shell is False
