# ruff: noqa: E402
import sys
from unittest.mock import Mock
import pytest
from tests.harness.setup.test_environment import TestEnvironment
from teddy_executor.core.ports.outbound.session_loop_guard import ISessionLoopGuard

# Globally mock litellm to prevent the expensive 1.2s import in all tests.
mock_litellm = Mock()

# Configure a "Safe-by-Default" response for litellm.completion()
_default_completion_mock = Mock()
_default_choice = Mock()
_default_choice.message.content = "# Mock Plan\nRationale: Test\n## Action Plan\n### READ\n- Resource: [README.md](/README.md)\n"
_default_completion_mock.choices = [_default_choice]
_default_completion_mock.model = "mock-model"

mock_litellm.completion.return_value = _default_completion_mock
mock_litellm.token_counter.return_value = 100

mock_litellm.completion_cost.return_value = 0.01
mock_litellm.validate_environment.return_value = {"missing_keys": []}
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
    mock_prompt_manager as mock_prompt_manager,
    mock_pyperclip as mock_pyperclip,
    mock_report_formatter as mock_report_formatter,
    mock_run_plan as mock_run_plan,
    mock_scraper as mock_scraper,
    mock_searcher as mock_searcher,
    mock_session_loop_guard as mock_session_loop_guard,
    mock_session_manager as mock_session_manager,
    mock_shell as mock_shell,
    mock_tree_gen as mock_tree_gen,
    mock_user_interactor as mock_user_interactor,
)


@pytest.fixture(autouse=True)
def guard_os_killpg(monkeypatch):
    """
    Poka-Yoke: Prevents poorly mocked processes (e.g., MagicMock which casts to 1)
    from sending SIGKILL to PID 1 or the test runner itself, which causes silent
    CI worker crashes.
    """
    import os

    original_killpg = getattr(os, "killpg", None)

    if original_killpg:
        my_pgid = os.getpgid(os.getpid())

        def safe_killpg(pgid, sig):
            if not isinstance(pgid, int):
                raise RuntimeError(
                    f"[Poka-Yoke] Blocked os.killpg with non-int PGID type: {type(pgid)}. Did you pass a MagicMock?"
                )
            if pgid <= 1:
                raise RuntimeError(
                    f"[Poka-Yoke] Blocked os.killpg on protected PGID: {pgid}. This would kill the container!"
                )
            if pgid == my_pgid:
                raise RuntimeError(
                    f"[Poka-Yoke] Blocked os.killpg on Test Runner's own PGID: {pgid}. This would kill pytest!"
                )
            return original_killpg(pgid, sig)

        monkeypatch.setattr(os, "killpg", safe_killpg)

    yield


def is_tee_active() -> bool:
    """Returns True if Tee is currently installed (sys.stderr is a _TeeWriter proxy).

    This helper is used by test fixtures to verify Tee installation timing
    and guard conditions.
    """
    from teddy_executor.core.utils.io import _TeeWriter

    return isinstance(sys.stderr, _TeeWriter)


@pytest.fixture
def tee_log_path():
    """Provides a temporary writeable history.log path for Tee testing.

    The fixture creates a temp file in the system temp directory, yields
    its Path, and cleans up after the test.
    """
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        path = Path(f.name)
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
def installed_tee(tee_log_path):
    """Installs Tee on the given log path and ensures cleanup after the test.

    Yields the Tee instance so tests can interact with it (e.g., check its
    state or write through the Tee). The Tee is properly uninstalled even
    if the test fails.
    """
    from teddy_executor.core.utils.io import Tee

    tee = Tee(tee_log_path)
    tee.__enter__()
    yield tee
    tee.__exit__(None, None, None)


@pytest.fixture
def container(monkeypatch):
    """
    Provides a fresh DI container for each test and automatically
    patches the global container in teddy_executor.container.
    """
    import teddy_executor.container
    from teddy_executor.container import create_container

    c = create_container()

    class TestSessionLoopGuard(ISessionLoopGuard):
        def should_continue(
            self, turn_count: int, cumulative_cost: float, interactive: bool
        ) -> bool:
            import os

            max_turns = int(os.getenv("TEDDY_MAX_TURNS", "1"))
            return turn_count < max_turns

    c.register(ISessionLoopGuard, TestSessionLoopGuard)

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


@pytest.fixture
def openrouter_mock(httpserver):
    """
    Configures the httpserver to respond to OpenRouter model requests.
    Returns the base URL of the mock server.
    """
    from tests.harness.setup.openrouter_mock_data import OPENROUTER_MODELS_RESPONSE

    httpserver.expect_request("/api/v1/models").respond_with_json(
        OPENROUTER_MODELS_RESPONSE
    )
    return httpserver.url_for("")


@pytest.fixture
def temp_cache_dir():
    """Provides a temporary directory for update cache tests.

    The directory is created in the system temp directory (avoids space-in-path
    issues on Windows) and is automatically cleaned up after the test.
    """
    import tempfile
    from pathlib import Path

    tmp_dir = Path(tempfile.mkdtemp(prefix="teddy_cache_"))
    yield tmp_dir
    import shutil

    shutil.rmtree(tmp_dir, ignore_errors=True)
