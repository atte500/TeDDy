import subprocess
from pathlib import Path


def test_di_boundary_hook_rejects_punq_in_core(tmp_path):
    # Setup: Create a violation file in a mock core directory
    # We use a real path relative to the project root for the grep command to work
    # as it would in pre-commit, but we'll simulate the check.
    violation_file = Path("src/teddy_executor/core/services/violation_spike.py")
    violation_file.parent.mkdir(parents=True, exist_ok=True)
    violation_file.write_text("import punq\n", encoding="utf-8")

    try:
        # Act: Run the command we intend to use in the pre-commit hook
        # Note: We exclude action_factory.py for now as it's a known violator
        # to be fixed in later deliverables.
        cmd = [
            "grep",
            "-rE",
            "import punq|from punq",
            "src/teddy_executor/core/",
            "--exclude=action_factory.py",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        # Assert: The command should find the violation and return exit code 0 (found matches)
        # In pre-commit, a 0 exit code from grep usually means it found something,
        # which we want to treat as a failure.
        assert result.returncode == 0
        assert "violation_spike.py" in result.stdout
        assert "import punq" in result.stdout

    finally:
        # Cleanup
        if violation_file.exists():
            violation_file.unlink()


def test_di_boundary_hook_passes_clean_core():
    # Setup: Ensure no violations (excluding known action_factory.py)
    cmd = [
        "grep",
        "-rE",
        "import punq|from punq",
        "src/teddy_executor/core/",
        "--exclude=action_factory.py",
        "--exclude=violation_spike.py",  # In case previous test failed cleanup
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Assert: Grep returns 1 if no matches are found.
    assert result.returncode == 1
