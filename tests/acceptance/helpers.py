import subprocess
import sys
from pathlib import Path
from typing import Optional

# Path to the teddy executable script
TEDDY_CMD_BASE = [sys.executable, "-m", "teddy"]


def run_teddy_with_plan_file(
    plan_file: Path, input: Optional[str] = None
) -> subprocess.CompletedProcess:
    """
    Helper function to run teddy with a given plan file path.
    Used for interactive tests where stdin is needed for user input.
    """
    cmd = TEDDY_CMD_BASE + ["--plan-file", str(plan_file)]
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


# The validate_teddy_output function was removed as it was based on a faulty
# assumption that the application would output raw YAML. The application outputs
# Markdown, which should be asserted against with string matching.
