import subprocess
import sys
from pathlib import Path
from typing import Optional, Any

import yaml
from teddy_executor.main import app
from typer.testing import CliRunner, Result

# Path to the teddy executable script
TEDDY_CMD_BASE = [sys.executable, "-m", "teddy_executor"]


runner = CliRunner(mix_stderr=False)


def run_teddy_with_plan_file(
    plan_file: Path, input: Optional[str] = None, auto_approve: bool = False
) -> subprocess.CompletedProcess:
    """
    Helper function to run teddy with a given plan file path.
    Used for interactive tests where stdin is needed for user input.
    """
    cmd = TEDDY_CMD_BASE + ["execute", str(plan_file)]
    if auto_approve:
        cmd.append("--yes")

    return subprocess.run(
        cmd,
        input=input,
        capture_output=True,
        text=True,
        cwd=plan_file.parent,
    )


def run_teddy_with_stdin(plan_content: str, cwd: Path) -> subprocess.CompletedProcess:
    """
    Helper function to run teddy by piping a plan string to stdin.
    This is no longer the primary way to execute plans. The default
    `execute` command now reads from a file or clipboard. This helper
    is kept for legacy tests that might still rely on it, but it's
    adapted to call the `execute` subcommand.
    """
    # Create a temporary file to hold the stdin content
    plan_file = cwd / "temp_plan_for_stdin_helper.yml"
    plan_file.write_text(plan_content)

    cmd = TEDDY_CMD_BASE + ["execute", str(plan_file), "--yes"]

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def _convert_paths(data: Any) -> Any:
    """Recursively converts Path objects to posix strings in a data structure."""
    if isinstance(data, Path):
        return data.as_posix()
    if isinstance(data, list):
        return [_convert_paths(item) for item in data]
    if isinstance(data, dict):
        return {key: _convert_paths(value) for key, value in data.items()}
    return data


def run_teddy_with_plan_structure(
    plan_structure: list | dict, cwd: Path
) -> subprocess.CompletedProcess:
    """
    Helper function that takes a Python data structure, converts it to a
    platform-agnostic YAML string, and runs teddy with it.
    """
    # Automatically convert any Path objects to posix strings
    sanitized_structure = _convert_paths(plan_structure)
    plan_content = yaml.dump(sanitized_structure)
    return run_teddy_with_stdin(plan_content, cwd=cwd)


def extract_yaml_from_stdout(output: str) -> str:
    """
    Extracts the YAML report from the full stdout, stripping any trailing
    human-readable messages.
    """
    separator = "\nExecution report copied to clipboard."
    if separator in output:
        return output.split(separator)[0].strip()
    return output.strip()


def parse_yaml_report(stdout: str) -> dict:
    """
    Parses the YAML report from teddy_executor's stdout after extracting it.
    """
    yaml_content = extract_yaml_from_stdout(stdout)
    return yaml.safe_load(yaml_content)


def run_teddy_command(
    args: list[str], cwd: Path, input: Optional[str] = None
) -> subprocess.CompletedProcess:
    """
    Helper function to run teddy with a list of command-line arguments.
    This is used for acceptance tests of non-plan-based commands like 'context'.
    """
    cmd = TEDDY_CMD_BASE + args
    return subprocess.run(
        cmd,
        input=input,
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def run_cli_command(
    monkeypatch, args: list[str], cwd: Path, input: Optional[str] = None
) -> Result:
    """
    Runs a teddy command using the CliRunner for in-process testing.
    """
    with monkeypatch.context() as m:
        m.chdir(cwd)
        return runner.invoke(app, args, input=input)


def run_cli_with_plan(monkeypatch, plan_structure: list | dict, cwd: Path) -> Result:
    """
    Runs the teddy 'execute' command with a plan structure using CliRunner.
    """
    sanitized_structure = _convert_paths(plan_structure)
    plan_content = yaml.dump(sanitized_structure)
    plan_file = cwd / "plan.yml"
    plan_file.write_text(plan_content)

    with monkeypatch.context() as m:
        m.chdir(cwd)
        return runner.invoke(app, ["execute", str(plan_file), "--yes"])
