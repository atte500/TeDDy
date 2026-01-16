from pathlib import Path
from typing import Optional, Any

import yaml
from teddy_executor.main import app
from typer.testing import CliRunner, Result


runner = CliRunner(mix_stderr=False)


def _convert_paths(data: Any) -> Any:
    """Recursively converts Path objects to posix strings in a data structure."""
    if isinstance(data, Path):
        return data.as_posix()
    if isinstance(data, list):
        return [_convert_paths(item) for item in data]
    if isinstance(data, dict):
        return {key: _convert_paths(value) for key, value in data.items()}
    return data


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
