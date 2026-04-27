from pathlib import Path
from typing import List, Optional
from typer.testing import CliRunner, Result
from teddy_executor.__main__ import app
from tests.harness.observers.report_parser import ReportParser


class CliTestAdapter:
    """
    Primary Driving Adapter in the Test Harness Triad.
    Wraps the CLI execution and provides structured observers.
    """

    def __init__(self, monkeypatch, cwd: Path):
        self._runner = CliRunner(mix_stderr=False)
        self._monkeypatch = monkeypatch
        self._cwd = cwd
        self._mock_editor_output: Optional[str] = None

    def set_mock_editor_output(self, content: str) -> None:
        """Sets the content that will be 'returned' by the external editor mock."""
        self._mock_editor_output = content

    def run_cli_command(
        self, args: List[str], cwd: Optional[Path] = None, input: Optional[str] = None
    ) -> Result:
        """Executes a CLI command in the specified workspace (defaults to self._cwd)."""
        target_cwd = cwd or self._cwd
        env = {}
        if self._mock_editor_output:
            env["TEDDY_TEST_MOCK_EDITOR_OUTPUT"] = self._mock_editor_output

        with self._monkeypatch.context() as m:
            m.chdir(target_cwd)
            result = self._runner.invoke(app, args, input=input, env=env)
            return result

    def run_execute_with_plan(
        self,
        plan_content: str,
        cwd: Optional[Path] = None,
        input: Optional[str] = None,
        interactive: bool = False,
        extra_args: Optional[List[str]] = None,
    ) -> Result:
        """
        Executes a plan via the '--plan-content' bypass and returns the Result.
        """
        args = ["execute", "--no-copy", "--plan-content", plan_content]
        if not interactive:
            args.append("--yes")
        if extra_args:
            args.extend(extra_args)
        return self.run_cli_command(args, cwd=cwd, input=input)

    def run_command(self, args: List[str], input: Optional[str] = None) -> Result:
        """Legacy alias for run_cli_command."""
        return self.run_cli_command(args, input=input)

    def run_start(self, args: List[str], input: Optional[str] = None) -> Result:
        """Runs the 'start' command."""
        return self.run_cli_command(["start"] + args, input=input)

    def run_resume(
        self,
        path: Optional[str] = None,
        no_copy: bool = True,
        interactive: bool = True,
        input: Optional[str] = None,
        extra_args: Optional[List[str]] = None,
    ) -> Result:
        """Runs the 'resume' command."""
        args = ["resume"]
        if path:
            args.append(path)
        if no_copy:
            args.append("--no-copy")
        if not interactive:
            args.append("--no-interactive")
        if extra_args:
            args.extend(extra_args)
        return self.run_cli_command(args, input=input)

    def execute_plan(
        self,
        plan_content: str,
        user_input: Optional[str] = None,
        interactive: bool = False,
        extra_args: Optional[List[str]] = None,
    ) -> ReportParser:
        """
        Executes a plan via the '--plan-content' bypass and returns a structured ReportParser.
        """
        result = self.run_execute_with_plan(
            plan_content,
            input=user_input,
            interactive=interactive,
            extra_args=extra_args,
        )

        if result.exception:
            import click

            if not isinstance(result.exception, (SystemExit, click.exceptions.Exit)):
                # Re-raise the exception to help debug test failures
                raise result.exception

        # Combine stdout and stderr so ReportParser can see both the summary and the report.
        return ReportParser(result.stdout + result.stderr)
