import subprocess
from unittest.mock import MagicMock
from tests.harness.setup.test_environment import TestEnvironment
from teddy_executor.core.ports.outbound.environment_inspector import (
    IEnvironmentInspector,
)


def test_get_environment_info(monkeypatch):
    """
    Tests that the SystemEnvironmentInspector returns a dictionary with
    the expected keys and non-empty string values.
    """
    env = TestEnvironment(monkeypatch).setup().with_real_inspector()
    inspector = env.get_service(IEnvironmentInspector)

    expected_keys = {
        "os_name",
        "os_version",
        "python_version",
        "cwd",
        "shell",
        "current_date",
        "current_time",
    }

    # Act
    env_info = inspector.get_environment_info()

    # Assert
    assert isinstance(env_info, dict)
    assert set(env_info.keys()) == expected_keys
    for key, value in env_info.items():
        assert isinstance(value, str), f"Value for '{key}' is not a string."
        assert value, f"Value for '{key}' is empty."


def test_get_git_status_returns_none_when_not_in_git_repo(monkeypatch):
    """
    Verify get_git_status returns None when the directory is not a git repository.
    """
    env = TestEnvironment(monkeypatch).setup().with_real_inspector()
    inspector = env.get_service(IEnvironmentInspector)

    # Mock subprocess.run to simulate 'not a git repository' error
    def mock_run(*_args, **_kwargs):
        raise subprocess.CalledProcessError(128, ["git", "status", "-s"])

    monkeypatch.setattr(subprocess, "run", mock_run)

    assert inspector.get_git_status() is None


def test_get_git_status_returns_concise_output_in_git_repo(monkeypatch):
    """
    Verify get_git_status returns the output of git status -s when in a repo.
    """
    env = TestEnvironment(monkeypatch).setup().with_real_inspector()
    inspector = env.get_service(IEnvironmentInspector)

    expected_output = " M src/main.py\n?? new_file.txt"
    mock_result = MagicMock()
    mock_result.stdout = expected_output
    mock_result.returncode = 0
    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=mock_result))

    assert inspector.get_git_status() == expected_output
