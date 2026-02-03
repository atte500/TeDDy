import pytest
import pyperclip
from unittest.mock import patch


@pytest.fixture(autouse=True)
def mock_pyperclip_for_acceptance_tests():
    """
    Automatically mock pyperclip for all acceptance tests.

    The `CliRunner` used in acceptance tests merges stdout and stderr.
    This causes the "copied to clipboard" confirmation message (sent to stderr)
    to be included in the stdout stream, breaking YAML parsing in tests.

    This fixture mocks `pyperclip.copy` to raise its specific exception,
    which the application is designed to handle gracefully by simply not
    printing the confirmation message. This fixes the tests without altering
    application logic.
    """
    with patch(
        "pyperclip.copy",
        side_effect=pyperclip.PyperclipException("Clipboard not available in test"),
    ) as mock_copy:
        yield mock_copy
