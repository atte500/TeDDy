import subprocess
import sys
import yaml
from pathlib import Path
from typing import Any, List, Dict, Optional

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


def validate_teddy_output(output: str) -> List[Dict[str, Any]]:
    """
    Parses the YAML output from teddy and validates its basic structure.
    Returns the parsed YAML content as a list of dictionaries.
    """
    try:
        parsed_output = yaml.safe_load(output)
    except yaml.YAMLError as e:
        raise AssertionError(
            f"Teddy output is not valid YAML: {e}\nOutput:\n{output}"
        ) from e

    if not isinstance(parsed_output, list):
        raise AssertionError(
            f"Teddy output is not a list of action reports.\nOutput:\n{output}"
        )

    return parsed_output
