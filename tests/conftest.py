"""
Standard Root Conftest
This file acts as the entry point for the TeDDy Test Harness. By using a
standard conftest.py instead of a pyproject.toml plugin, we ensure that
pytest-cov starts tracking coverage BEFORE our core modules are imported.
"""

import functools
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.harness.setup.composition import (
    container,
    mock_config,
    mock_user_interactor,
    mock_fs,
    mock_env,
    mock_shell,
    mock_scraper,
    mock_searcher,
    mock_session_manager,
    mock_planning_service,
    mock_tree_gen,
    mock_action_factory,
    mock_plan_parser,
    mock_plan_validator,
    mock_plan_reviewer,
    mock_action_dispatcher,
    mock_run_plan,
    mock_context_service,
    mock_edit_simulator,
    mock_inspector,
    mock_report_formatter,
    mock_llm_client,
    mock_prompt_manager,
    mock_pyperclip,
    env,
    real_env,
)


def pytest_configure(config):
    """
    Systemic Fix for Windows CI: Force UTF-8 as the default for all file I/O
    in tests. This prevents UnicodeEncodeError on Windows runners when
    handling emojis or non-ASCII characters in plans, reports, or source code.
    """
    original_write_text = Path.write_text
    original_read_text = Path.read_text

    @functools.wraps(original_write_text)
    def utf8_write_text(self, data, encoding=None, errors=None, newline=None):
        if encoding is None:
            encoding = "utf-8"
        return original_write_text(
            self, data, encoding=encoding, errors=errors, newline=newline
        )

    @functools.wraps(original_read_text)
    def utf8_read_text(self, encoding=None, errors=None):
        if encoding is None:
            encoding = "utf-8"
        return original_read_text(self, encoding=encoding, errors=errors)

    Path.write_text = utf8_write_text
    Path.read_text = utf8_read_text


# Exporting these fixtures makes them globally available to all test suites
__all__ = [
    "container",
    "mock_config",
    "mock_user_interactor",
    "mock_fs",
    "mock_env",
    "mock_shell",
    "mock_scraper",
    "mock_searcher",
    "mock_session_manager",
    "mock_planning_service",
    "mock_tree_gen",
    "mock_action_factory",
    "mock_plan_parser",
    "mock_plan_validator",
    "mock_plan_reviewer",
    "mock_action_dispatcher",
    "mock_run_plan",
    "mock_context_service",
    "mock_edit_simulator",
    "mock_inspector",
    "mock_report_formatter",
    "mock_llm_client",
    "mock_prompt_manager",
    "mock_pyperclip",
    "env",
    "real_env",
]


@pytest.fixture(scope="session", autouse=True)
def patch_socket_getfqdn():
    """
    Systemic Fix for macOS CI: socket.getfqdn('127.0.0.1') hangs on some runners.
    By patching it session-wide to return 'localhost', we bypass the DNS lookup
    bottleneck for pytest-httpserver and other networking utilities.
    """
    with patch("socket.getfqdn", return_value="localhost"):
        yield


@pytest.fixture(autouse=True)
def reset_formatter_singleton():
    """Ensures test isolation for the report formatter singleton."""
    from teddy_executor.core.services.markdown_report_formatter import (
        MarkdownReportFormatter,
    )

    MarkdownReportFormatter._reset_singleton()
    yield
    MarkdownReportFormatter._reset_singleton()


@pytest.fixture(autouse=True)
def clean_test_env():
    """Defensive guard: ensure isolation of testing hooks and CWD state."""
    import os
    from teddy_executor.adapters.inbound.cli_helpers import find_project_root

    # Capture initial state
    project_root = find_project_root()
    var = "TEDDY_TEST_MOCK_EDITOR_OUTPUT"

    if var in os.environ:
        del os.environ[var]

    yield

    # Restore state
    if var in os.environ:
        del os.environ[var]

    # Systemic Fix for Windows CI worker crashes: ensure CWD is restored
    # to the project root after every test, preventing state leakage.
    try:
        os.chdir(project_root)
    except Exception:
        pass
