# ruff: noqa: E402
import sys
from unittest.mock import MagicMock
import pytest
from tests.harness.setup.test_environment import TestEnvironment

# Globally mock litellm to prevent the expensive 1.2s import in all tests.
mock_litellm = MagicMock()

# Configure a "Safe-by-Default" response for litellm.completion()
_default_completion_mock = MagicMock()
_default_choice = MagicMock()
_default_choice.message.content = "# Mock Plan\nRationale: Test\n## Action Plan\n### READ\n- Resource: [README.md](/README.md)\n"
_default_completion_mock.choices = [_default_choice]
_default_completion_mock.model = "mock-model"

mock_litellm.completion.return_value = _default_completion_mock
mock_litellm.token_counter.return_value = 100
mock_litellm.completion_cost.return_value = 0.01

sys.modules["litellm"] = mock_litellm

# Re-export mocks for standard fixtures
from tests.harness.setup.mocks import (
    mock_action_dispatcher as mock_action_dispatcher,
    mock_action_factory as mock_action_factory,
    mock_config as mock_config,
    mock_context_service as mock_context_service,
    mock_edit_simulator as mock_edit_simulator,
    mock_env as mock_env,
    mock_fs as mock_fs,
    mock_inspector as mock_inspector,
    mock_llm_client as mock_llm_client,
    mock_plan_parser as mock_plan_parser,
    mock_plan_reviewer as mock_plan_reviewer,
    mock_plan_validator as mock_plan_validator,
    mock_planning_service as mock_planning_service,
    mock_pyperclip as mock_pyperclip,
    mock_report_formatter as mock_report_formatter,
    mock_run_plan as mock_run_plan,
    mock_scraper as mock_scraper,
    mock_searcher as mock_searcher,
    mock_session_manager as mock_session_manager,
    mock_shell as mock_shell,
    mock_tree_gen as mock_tree_gen,
    mock_user_interactor as mock_user_interactor,
)


@pytest.fixture
def container(monkeypatch):
    """
    Provides a fresh DI container for each test and automatically
    patches the global container in teddy_executor.container.
    """
    import teddy_executor.container
    from teddy_executor.container import create_container

    c = create_container()
    # Force the global container to be this fresh instance
    monkeypatch.setattr(teddy_executor.container, "_container", c)
    return c


@pytest.fixture
def env(monkeypatch, container):
    """
    Standard fixture for a managed TestEnvironment with Mocks.
    Automatically handles workspace creation and cleanup.
    """
    e = TestEnvironment(monkeypatch)
    e.container = container
    e.setup()
    yield e
    e.teardown()


@pytest.fixture
def real_env(monkeypatch):
    """
    Managed TestEnvironment with real Filesystem and Shell.
    """
    e = TestEnvironment(monkeypatch)
    e.setup()
    e.with_real_filesystem()
    e.with_real_shell()
    e.with_real_init_service()
    yield e
    e.teardown()
