from pathlib import Path
from typing import List, Optional
from typer.testing import CliRunner, Result
from teddy_executor.__main__ import app
from tests.observers.report_parser import ReportParser


class CliTestAdapter:
    """
    Primary Driving Adapter in the Test Harness Triad.
    Wraps the CLI execution and provides structured observers.
    """

    def __init__(self, monkeypatch, cwd: Path):
        self._runner = CliRunner()
        self._monkeypatch = monkeypatch
        self._cwd = cwd

    def run_command(self, args: List[str], input: Optional[str] = None) -> Result:
        """Executes a CLI command in the test workspace."""
        with self._monkeypatch.context() as m:
            m.chdir(self._cwd)
            return self._runner.invoke(app, args, input=input)

    def execute_plan(
        self, plan_content: str, user_input: Optional[str] = None
    ) -> ReportParser:
        """
        Executes a plan via the '--plan-content' bypass and returns a structured ReportParser.
        """
        args = ["execute", "--yes", "--no-copy", "--plan-content", plan_content]
        result = self.run_command(args, input=user_input)

        if result.exception:
            # Re-raise the exception to help debug test failures
            raise result.exception

        return ReportParser(result.stdout)
