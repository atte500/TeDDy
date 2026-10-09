import shutil
import subprocess

import pytest


@pytest.mark.skipif(
    shutil.which("grep") is None,
    reason="grep not available on PATH (Windows)",
)
def test_di_boundary_hook_rejects_punq_in_core(tmp_path):
    # Setup: plant the violation inside a TEMPORARY core tree. The check must NOT
    # write into the live src/teddy_executor/core/ directory: under pytest-xdist
    # the transient file was present when one worker snapshotted `git status`
    # and gone by another worker's snapshot, tripping the session-scoped
    # `_assert_no_test_pollution` Poka-Yoke with a bogus "files that
    # unexpectedly disappeared" failure.
    core_dir = tmp_path / "core" / "services"
    core_dir.mkdir(parents=True)
    (core_dir / "violation_spike.py").write_text("import punq\n", encoding="utf-8")

    # Act: run the same grep pattern the pre-commit hook uses, scoped to the
    # temporary core tree.
    cmd = [
        "grep",
        "-rE",
        "import punq|from punq",
        str(tmp_path / "core"),
        "--exclude=action_factory.py",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Assert: the command finds the violation and returns exit code 0 (matches).
    assert result.returncode == 0
    assert "violation_spike.py" in result.stdout
    assert "import punq" in result.stdout


@pytest.mark.skipif(
    shutil.which("grep") is None,
    reason="grep not available on PATH (Windows)",
)
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
