import subprocess
import sys
from pathlib import Path
from typing import Optional
import yaml

# Path to the teddy executable script
TEDDY_CMD_BASE = [sys.executable, "-m", "teddy"]


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


def parse_yaml_report(stdout: str) -> dict:
    """Parses the YAML report from teddy's stdout."""
    return yaml.safe_load(stdout)
