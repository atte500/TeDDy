import subprocess
import sys
from pathlib import Path
from typing import Optional

# Path to the teddy executable script
TEDDY_CMD = [sys.executable, "-m", "teddy", "--plan-file"]


def run_teddy_as_subprocess(
    plan_file: Path, input: Optional[str] = None
) -> subprocess.CompletedProcess:
    """Helper function to run teddy with a given plan file."""
    return subprocess.run(
        TEDDY_CMD + [str(plan_file)],
        input=input,
        capture_output=True,
        text=True,
        cwd=plan_file.parent,
    )


# The validate_teddy_output function was removed as it was based on a faulty
# assumption that the application would output raw YAML. The application outputs
# Markdown, which should be asserted against with string matching.
