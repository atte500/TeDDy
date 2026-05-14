import subprocess
from tests.harness.setup.mocking import POSIXPathMock
from teddy_executor.adapters.outbound.system_environment_inspector import (
    SystemEnvironmentInspector,
)


def test_get_environment_info(monkeypatch):
    """
    Tests that the SystemEnvironmentInspector returns a dictionary with
    the expected keys and non-empty string values.
    """
    inspector = SystemEnvironmentInspector()

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

    # Mock subprocess.run to simulate 'not a git repository' error
    def mock_run(*_args, **_kwargs):
        raise subprocess.CalledProcessError(128, ["git", "status", "-s"])

    inspector = SystemEnvironmentInspector(run_func=mock_run)

    assert inspector.get_git_status() is None


def test_get_git_status_returns_concise_output_in_git_repo(monkeypatch):
    """
    Verify get_git_status returns the output of git status -s when in a repo.
    """
    expected_output = " M src/main.py\n?? new_file.txt"
    mock_result = POSIXPathMock()
    mock_result.stdout = expected_output
    mock_result.returncode = 0
    mock_run = POSIXPathMock(return_value=mock_result)

    inspector = SystemEnvironmentInspector(run_func=mock_run)

    assert inspector.get_git_status() == expected_output


def test_get_git_status_isolates_stdin(monkeypatch):
    """
    Verify get_git_status isolates stdin to prevent concurrent CI workers from hanging.
    """
    mock_run = POSIXPathMock()
    # Need to return a valid POSIXPathMock for the result so .stdout doesn't fail
    mock_run.return_value = POSIXPathMock(stdout="")

    inspector = SystemEnvironmentInspector(run_func=mock_run)

    inspector.get_git_status()

    mock_run.assert_called_once()
    _, kwargs = mock_run.call_args
    assert "stdin" in kwargs, "stdin missing from subprocess.run call"
    assert kwargs["stdin"] == subprocess.DEVNULL, "stdin must be DEVNULL"
