from contextlib import contextmanager
from pathlib import Path
import tempfile
from typing import Generator, Optional, Any

import yaml
from teddy_executor.main import app
from typer.testing import CliRunner, Result


runner = CliRunner()


def _convert_paths(data: Any) -> Any:
    """Recursively converts Path objects and strings to posix format."""
    if isinstance(data, Path):
        return data.as_posix()
    if isinstance(data, str):
        # Normalize backslashes to forward slashes to avoid YAML escaping issues on Windows.
        # This is safe because both Python and the shell accept forward slashes on Windows.
        return data.replace("\\", "/")
    if isinstance(data, list):
        return [_convert_paths(item) for item in data]
    if isinstance(data, dict):
        return {key: _convert_paths(value) for key, value in data.items()}
    return data


def extract_yaml_from_stdout(output: str) -> str:
    """
    Extracts the YAML report from the full stdout.

    This is robust against preceding interactive prompts and trailing messages
    by searching for the known start of the YAML report.
    """
    # The YAML report reliably starts with "run_summary:".
    # Some interactive prompts might add a "---" diff output first.
    # The report itself might start with a document separator "---".
    # Find the last occurrence of "---" if it exists, otherwise start from the beginning.

    lines = output.splitlines()
    start_index = 0
    for i, line in enumerate(lines):
        # The YAML report always contains this key.
        if line.strip().startswith("run_summary:"):
            # The report might start with a '---' separator on the line above.
            if i > 0 and lines[i - 1].strip() == "---":
                start_index = i - 1
            else:
                start_index = i
            break

    yaml_lines = lines[start_index:]

    # Strip any trailing clipboard messages
    yaml_str = "\n".join(yaml_lines)
    separator = "\nExecution report copied to clipboard."
    if separator in yaml_str:
        yaml_str = yaml_str.split(separator)[0]

    return yaml_str


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


@contextmanager
def create_plan_file(
    content: str, extension: str = ".yml"
) -> Generator[Path, None, None]:
    """A context manager to create a temporary plan file."""
    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=extension, encoding="utf-8"
    ) as tmp_file:
        tmp_file.write(content)
        plan_path = Path(tmp_file.name)
    try:
        yield plan_path
    finally:
        if plan_path.exists():
            plan_path.unlink()
