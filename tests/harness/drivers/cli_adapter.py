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
        self._runner = CliRunner()
        self._monkeypatch = monkeypatch
        self._cwd = cwd

    def run_cli_command(
        self, args: List[str], cwd: Optional[Path] = None, input: Optional[str] = None
    ) -> Result:
        """Executes a CLI command in the specified workspace (defaults to self._cwd)."""
        target_cwd = cwd or self._cwd
        with self._monkeypatch.context() as m:
            m.chdir(target_cwd)
            result = self._runner.invoke(app, args, input=input)
            # Ensure stderr is never None to avoid attribute errors in tests
            if result.stderr is None:
                result.stderr = ""
            return result

    def run_execute_with_plan(
        self,
        plan_content: str,
        cwd: Optional[Path] = None,
        input: Optional[str] = None,
        interactive: bool = False,
    ) -> Result:
        """
        Executes a plan via the '--plan-content' bypass and returns the Result.
        """
        args = ["execute", "--no-copy", "--plan-content", plan_content]
        if not interactive:
            args.append("--yes")
        return self.run_cli_command(args, cwd=cwd, input=input)

    def run_command(self, args: List[str], input: Optional[str] = None) -> Result:
        """Legacy alias for run_cli_command."""
        return self.run_cli_command(args, input=input)

    def run_start(self, args: List[str], input: Optional[str] = None) -> Result:
        """Runs the 'start' command."""
        return self.run_cli_command(["start"] + args, input=input)

    def run_resume(self, session_path: str, input: Optional[str] = None) -> Result:
        """Runs the 'resume' command."""
        return self.run_cli_command(["resume", session_path], input=input)

    def execute_plan(
        self,
        plan_content: str,
        user_input: Optional[str] = None,
        interactive: bool = False,
    ) -> ReportParser:
        """
        Executes a plan via the '--plan-content' bypass and returns a structured ReportParser.
        """
        result = self.run_execute_with_plan(
            plan_content, input=user_input, interactive=interactive
        )

        if result.exception:
            import click

            if not isinstance(result.exception, (SystemExit, click.exceptions.Exit)):
                # Re-raise the exception to help debug test failures
                raise result.exception

        return ReportParser(result.stdout)
