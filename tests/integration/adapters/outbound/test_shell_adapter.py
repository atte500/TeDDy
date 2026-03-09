import os
import shutil
import sys
from pathlib import Path

import pytest
from teddy_executor.adapters.outbound.shell_adapter import ShellAdapter


def test_shell_adapter_executes_command_successfully():
    """
    Tests that the ShellAdapter can run a successful command and capture its output.
    """
    # ARRANGE
    adapter = ShellAdapter()
    # Use sys.executable to ensure the command is platform-agnostic
    command = f"{sys.executable} -c \"print('hello from shell')\""

    # ACT
    result = adapter.execute(command)

    # ASSERT
    assert result["return_code"] == 0
    assert result["stdout"].strip() == "hello from shell"
    assert result["stderr"] == ""


def test_shell_adapter_handles_failed_command():
    """
    Tests that the ShellAdapter captures stderr and a non-zero exit code
    for a failed command.
    """
    # ARRANGE
    adapter = ShellAdapter()
    # Using a command that is very unlikely to exist
    command = "nonexistentcommand12345"

    # ACT
    result = adapter.execute(command)

    # ASSERT
    assert result["return_code"] != 0
    assert result["stdout"] == ""
    # Check that stderr contains the correct error message (platform dependent)
    # POSIX: "No such file or directory"
    # Windows: "is not recognized as an internal or external command" or "The system cannot find the file specified"
    # The exact error message for a failed command can vary between shells
    # (e.g., 'command not found' vs 'not found'). We check for a common substring.
    assert (
        "not found" in result["stderr"]
        or "not recognized" in result["stderr"]
        or "cannot find the file" in result["stderr"]
    )


def test_shell_adapter_executes_in_specified_cwd():
    """
    Tests that the ShellAdapter correctly executes a command in the specified
    current working directory (cwd).
    """
    adapter = ShellAdapter()
    # Create a temporary directory *inside* the project root to comply with security validation
    temp_dir_name = "temp_test_dir_cwd"
    temp_dir_path = os.path.join(os.getcwd(), temp_dir_name)
    os.makedirs(temp_dir_path, exist_ok=True)

    try:
        # Create a file in the temp directory
        with open(
            os.path.join(temp_dir_path, "testfile.txt"), "w", encoding="utf-8"
        ) as f:
            f.write("hello")

        # Command to list contents of the directory
        command = "ls" if sys.platform != "win32" else "dir"
        # We can use a relative path for the cwd
        result = adapter.execute(command, cwd=temp_dir_name)

        assert result["return_code"] == 0
        assert "testfile.txt" in result["stdout"]

    finally:
        # Clean up the temporary directory
        shutil.rmtree(temp_dir_path)


def test_shell_adapter_preserves_parent_environment():
    """
    Tests that the ShellAdapter passes environment variables correctly
    while also preserving the parent process's environment.
    """
    adapter = ShellAdapter()
    # This command checks if the PATH variable exists and prints a custom var.
    # On Windows, we use %VAR%, on Unix-like systems, we use $VAR.
    if sys.platform == "win32":
        command = 'cmd /c "echo %PATH% && echo %CUSTOM_VAR%"'
    else:
        command = 'sh -c "echo $PATH && echo $CUSTOM_VAR"'

    env = {"CUSTOM_VAR": "custom_value"}
    result = adapter.execute(command, env=env)

    assert result["return_code"] == 0
    # Check that PATH from parent env is not empty
    assert result["stdout"].splitlines()[0] != ""
    # Check that the custom env var was passed correctly
    assert result["stdout"].splitlines()[1] == "custom_value"


@pytest.mark.timeout(10)  # Add a timeout to prevent hanging indefinitely
def test_shell_adapter_handles_multiline_command_safely():
    """
    Tests that the ShellAdapter can execute a command with multi-line arguments
    without hanging. This simulates the `git commit -m "..."` issue.
    """
    adapter = ShellAdapter()
    # Using python -c is a safe, cross-platform way to test multi-line args
    multiline_string = "first line\nsecond line"
    command = f"{sys.executable} -c \"print('''{multiline_string}''')\""

    result = adapter.execute(command)

    assert result["return_code"] == 0
    assert result["stdout"].strip() == multiline_string.strip()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX specific shell features")
def test_shell_adapter_handles_wildcards_on_posix():
    """Verify that the shell adapter can execute commands with wildcards."""
    adapter = ShellAdapter()
    # Create a temporary directory *inside* the project root to comply with security validation
    temp_dir_name = "temp_test_dir_wildcard"
    temp_dir_path = os.path.join(os.getcwd(), temp_dir_name)
    os.makedirs(temp_dir_path, exist_ok=True)

    try:
        Path(os.path.join(temp_dir_path, "test1.py")).touch()
        Path(os.path.join(temp_dir_path, "test2.py")).touch()
        Path(os.path.join(temp_dir_path, "other.txt")).touch()

        result = adapter.execute("ls *.py", cwd=temp_dir_name)

        assert result["return_code"] == 0
        assert "test1.py" in result["stdout"]
        assert "test2.py" in result["stdout"]
        assert "other.txt" not in result["stdout"]
    finally:
        shutil.rmtree(temp_dir_path)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX specific shell features")
def test_shell_adapter_handles_pipes_on_posix():
    """Verify that the shell adapter can execute commands with pipes."""
    adapter = ShellAdapter()
    command = 'echo "hello world" | grep "world"'

    result = adapter.execute(command)

    assert result["return_code"] == 0
    assert "hello world" in result["stdout"]


def test_shell_adapter_handles_command_chaining():
    """Verify that the shell adapter can execute chained commands (e.g., &&)."""
    adapter = ShellAdapter()
    if sys.platform == "win32":
        command = "echo first && echo second"
    else:
        command = 'echo "first" && echo "second"'

    result = adapter.execute(command)

    assert result["return_code"] == 0
    assert "first" in result["stdout"]
    assert "second" in result["stdout"]


def test_shell_adapter_preserves_env_across_chained_commands():
    """Verify that env variables are preserved across chained commands."""
    adapter = ShellAdapter()
    # Use python to print env to avoid CMD's expansion quirks on Windows
    if sys.platform == "win32":
        command = f"set TEST_VAR=chained && {sys.executable} -c \"import os; print(os.environ.get('TEST_VAR'))\""
    else:
        command = f"export TEST_VAR=chained && {sys.executable} -c \"import os; print(os.environ.get('TEST_VAR'))\""

    result = adapter.execute(command)

    assert result["return_code"] == 0
    assert "chained" in result["stdout"].strip()
