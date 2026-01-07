import subprocess
import sys
from pathlib import Path
from typing import Optional, Any
import yaml

# Path to the teddy executable script
TEDDY_CMD_BASE = [sys.executable, "-m", "teddy_executor"]


def run_teddy_with_plan_file(
    plan_file: Path, input: Optional[str] = None, auto_approve: bool = False
) -> subprocess.CompletedProcess:
    """
    Helper function to run teddy with a given plan file path.
    Used for interactive tests where stdin is needed for user input.
    """
    cmd = TEDDY_CMD_BASE + ["--plan-file", str(plan_file)]
    if auto_approve:
        cmd.append("-y")

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
    Used for non-interactive tests.
    """
    return subprocess.run(
        TEDDY_CMD_BASE,
        input=plan_content,
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


def parse_yaml_report(stdout: str) -> dict:
    """Parses the YAML report from teddy_executor's stdout."""
    return yaml.safe_load(stdout)


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
