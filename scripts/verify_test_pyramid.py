#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

# --- Configuration ---
ROOT_DIR = Path(__file__).parent.parent
ACCEPTANCE_DIR = ROOT_DIR / "tests" / "acceptance"
INTEGRATION_DIR = ROOT_DIR / "tests" / "integration"
UNIT_DIR = ROOT_DIR / "tests" / "unit"
# ---

def count_tests_in_dir(directory: Path) -> int:
    """Counts 'def test_' occurrences by walking python files."""
    if not directory.is_dir():
        print(f"Error: Directory not found at '{directory}'", file=sys.stderr)
        return 0

    total_count = 0
    for py_file in directory.rglob("test_*.py"):
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                for line in f:
                    # Check for start of a test function definition
                    if line.strip().startswith("def test_"):
                        total_count += 1
        except Exception as e:
            print(f"Error reading file {py_file}: {e}", file=sys.stderr)
    return total_count

def main():
    """
    Main function to verify the test pyramid structure and exit with a status
    code indicating success or failure.
    """
    print("--- Verifying Test Pyramid Structure ---")

    acceptance_count = count_tests_in_dir(ACCEPTANCE_DIR)
    integration_count = count_tests_in_dir(INTEGRATION_DIR)
    unit_count = count_tests_in_dir(UNIT_DIR)

    print(f"Acceptance Tests:  {acceptance_count}")
    print(f"Integration Tests: {integration_count}")
    print(f"Unit Tests:        {unit_count}")

    # The simple rule: Acceptance < Integration < Unit
    pyramid_is_healthy = (
        acceptance_count < integration_count < unit_count
    )

    if pyramid_is_healthy:
        print("\n✅ Test pyramid structure is healthy.")
        sys.exit(0)
    else:
        print("\n❌ ERROR: Test pyramid structure is violated!", file=sys.stderr)
        print("The rule is: Acceptance < Integration < Unit", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
