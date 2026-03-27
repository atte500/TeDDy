"""
Standard Root Conftest
This file acts as the entry point for the TeDDy Test Harness. By using a
standard conftest.py instead of a pyproject.toml plugin, we ensure that
pytest-cov starts tracking coverage BEFORE our core modules are imported.
"""

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
    mock_pyperclip,
    env,
    real_env,
)

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
    "mock_pyperclip",
    "env",
    "real_env",
]


@pytest.fixture(autouse=True)
def reset_formatter_singleton():
    """Ensures test isolation for the report formatter singleton."""
    from teddy_executor.core.services.markdown_report_formatter import (
        MarkdownReportFormatter,
    )

    MarkdownReportFormatter._reset_singleton()
    yield
    MarkdownReportFormatter._reset_singleton()
