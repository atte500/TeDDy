# This import will fail
from teddy.adapters.outbound.shell_adapter import ShellAdapter


def test_shell_adapter_executes_command_successfully():
    """
    Tests that the ShellAdapter can run a successful command and capture its output.
    """
    # ARRANGE
    adapter = ShellAdapter()
    command = 'echo "hello from shell"'

    # ACT
    result = adapter.run(command)

    # ASSERT
    assert result.return_code == 0
    assert result.stdout.strip() == "hello from shell"
    assert result.stderr == ""


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
    result = adapter.run(command)

    # ASSERT
    assert result.return_code != 0
    assert result.stdout == ""
    # Check that stderr contains a "not found" or "not recognized" message
    assert "not found" in result.stderr or "not recognized" in result.stderr
