"""Unit tests for the shared in-memory ``IShellExecutor`` double."""

from teddy_executor.core.domain.models.shell_output import ShellOutput
from teddy_executor.core.ports.outbound.shell_executor import IShellExecutor
from tests.harness.setup.fake_shell_executor import FakeShellExecutor


def test_defaults_to_a_successful_empty_run_and_records_the_command() -> None:
    shell = FakeShellExecutor()

    output = shell.execute("ls -la")

    assert output == {"stdout": "", "stderr": "", "return_code": 0}
    assert shell.commands == ["ls -la"]


def test_returns_the_scripted_output_for_every_command() -> None:
    scripted = ShellOutput(stdout="", stderr="", return_code=-2, interrupted=True)
    shell = FakeShellExecutor(output=scripted)

    assert shell.execute("sleep 30") is scripted


def test_injected_callback_runs_inside_execute_and_supplies_the_output() -> None:
    seen: list[str] = []

    def on_execute(command: str) -> ShellOutput:
        seen.append(command)
        return ShellOutput(stdout="", stderr="", return_code=-2, interrupted=True)

    shell = FakeShellExecutor(on_execute=on_execute)

    output = shell.execute("sleep 30")

    assert seen == ["sleep 30"]
    assert output["interrupted"] is True
    assert shell.commands == ["sleep 30"]


def test_conforms_to_the_shell_executor_port() -> None:
    assert isinstance(FakeShellExecutor(), IShellExecutor)
