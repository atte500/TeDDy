import sys
from pathlib import Path

import pytest
from tests.harness.setup.test_environment import TestEnvironment
from teddy_executor.core.ports.outbound import IShellExecutor


@pytest.fixture
def adapter(monkeypatch, tmp_path):
    """
    Provides a real ShellAdapter resolved via the Test Harness.
    """
    # ShellAdapter needs a real SystemEnvironment to get the PATH
    from teddy_executor.core.ports.outbound import ISystemEnvironment
    from teddy_executor.adapters.outbound.system_environment_adapter import (
        SystemEnvironmentAdapter,
    )

    env = TestEnvironment(monkeypatch, tmp_path).setup().with_real_shell()
    env.container.register(ISystemEnvironment, SystemEnvironmentAdapter)

    return env.get_service(IShellExecutor)


def test_shell_adapter_executes_command_successfully(adapter):
    """
    Tests that the ShellAdapter can run a successful command and capture its output.
    """
    # ARRANGE
    # Use sys.executable to ensure the command is platform-agnostic
    command = f"{sys.executable} -c \"print('hello from shell')\""

    # ACT
    result = adapter.execute(command)

    # ASSERT
    assert result["return_code"] == 0
    assert result["stdout"].strip() == "hello from shell"
    assert result["stderr"] == ""


def test_shell_adapter_handles_failed_command(adapter):
    """
    Tests that the ShellAdapter captures stderr and a non-zero exit code
    for a failed command.
    """
    # ARRANGE
    # Using a command that is very unlikely to exist
    command = "nonexistentcommand12345"

    # ACT
    result = adapter.execute(command)

    # ASSERT
    assert result["return_code"] != 0
    assert result["stdout"] == ""
    # Check that stderr contains the correct error message (platform dependent)
    assert (
        "not found" in result["stderr"]
        or "not recognized" in result["stderr"]
        or "cannot find the file" in result["stderr"]
    )


def test_shell_adapter_executes_in_specified_cwd(adapter):
    """
    Tests that the ShellAdapter correctly executes a command in the specified
    current working directory (cwd).
    """
    # ARRANGE
    # Since adapter fixture already chdir'd to tmp_path, we use relative paths
    temp_dir_name = "temp_test_dir_cwd"
    Path(temp_dir_name).mkdir(exist_ok=True)
    (Path(temp_dir_name) / "testfile.txt").write_text("hello", encoding="utf-8")

    # Command to list contents of the directory
    command = "ls" if sys.platform != "win32" else "dir"

    # ACT
    result = adapter.execute(command, cwd=temp_dir_name)

    # ASSERT
    assert result["return_code"] == 0
    assert "testfile.txt" in result["stdout"]


def test_shell_adapter_preserves_parent_environment(adapter):
    """
    Tests that the ShellAdapter passes environment variables correctly
    while also preserving the parent process's environment.
    """
    # ARRANGE
    # This command checks if the PATH variable exists and prints a custom var.
    if sys.platform == "win32":
        command = 'cmd /c "echo %PATH% && echo %CUSTOM_VAR%"'
    else:
        command = 'sh -c "echo $PATH && echo $CUSTOM_VAR"'

    env = {"CUSTOM_VAR": "custom_value"}

    # ACT
    result = adapter.execute(command, env=env)

    # ASSERT
    assert result["return_code"] == 0
    # Check that PATH from parent env is not empty
    assert result["stdout"].splitlines()[0] != ""
    # Check that the custom env var was passed correctly
    assert result["stdout"].splitlines()[1].strip() == "custom_value"


@pytest.mark.timeout(10)
def test_shell_adapter_handles_multiline_command_safely(adapter):
    """
    Tests that the ShellAdapter can execute a command with multi-line arguments
    without hanging.
    """
    # ARRANGE
    multiline_string = "first line\nsecond line"
    command = f"{sys.executable} -c \"print('''{multiline_string}''')\""

    # ACT
    result = adapter.execute(command)

    # ASSERT
    assert result["return_code"] == 0
    assert result["stdout"].strip() == multiline_string.strip()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX specific shell features")
def test_shell_adapter_handles_wildcards_on_posix(adapter):
    """Verify that the shell adapter can execute commands with wildcards."""
    # ARRANGE
    temp_dir_name = "temp_test_dir_wildcard"
    Path(temp_dir_name).mkdir(exist_ok=True)
    (Path(temp_dir_name) / "test1.py").touch()
    (Path(temp_dir_name) / "test2.py").touch()
    (Path(temp_dir_name) / "other.txt").touch()

    # ACT
    result = adapter.execute("ls *.py", cwd=temp_dir_name)

    # ASSERT
    assert result["return_code"] == 0
    assert "test1.py" in result["stdout"]
    assert "test2.py" in result["stdout"]
    assert "other.txt" not in result["stdout"]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX specific shell features")
def test_shell_adapter_handles_pipes_on_posix(adapter):
    """Verify that the shell adapter can execute commands with pipes."""
    # ARRANGE
    command = 'echo "hello world" | grep "world"'

    # ACT
    result = adapter.execute(command)

    # ASSERT
    assert result["return_code"] == 0
    assert "hello world" in result["stdout"]


def test_shell_adapter_handles_command_chaining(adapter):
    """Verify that the shell adapter can execute chained commands (e.g., &&)."""
    # ARRANGE
    if sys.platform == "win32":
        command = "echo first && echo second"
    else:
        command = 'echo "first" && echo "second"'

    # ACT
    result = adapter.execute(command)

    # ASSERT
    assert result["return_code"] == 0
    assert "first" in result["stdout"]
    assert "second" in result["stdout"]


def test_shell_adapter_preserves_env_across_chained_commands(adapter):
    """Verify that env variables are preserved across chained commands."""
    # ARRANGE
    if sys.platform == "win32":
        command = f"set TEST_VAR=chained && {sys.executable} -c \"import os; print(os.environ.get('TEST_VAR'))\""
    else:
        command = f"export TEST_VAR=chained && {sys.executable} -c \"import os; print(os.environ.get('TEST_VAR'))\""

    # ACT
    result = adapter.execute(command)

    # ASSERT
    assert result["return_code"] == 0
    assert "chained" in result["stdout"].strip()
