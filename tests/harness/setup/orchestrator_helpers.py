"""Test fixtures and helpers for SessionOrchestrator-related tests.

Provides reusable test doubles for constructing a SessionOrchestrator
with mocked dependencies, suitable for session-mode and non-session-mode tests.
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock  # noqa: TID251


from teddy_executor.core.domain.models.execution_report import (
    ExecutionReport,
    RunStatus,
    RunSummary,
)
from teddy_executor.core.services.session_orchestrator import SessionOrchestrator
from teddy_executor.core.services.session_replanner import SessionReplanner


def build_mocked_orchestrator(
    session_root: Path, plan_path: str
) -> SessionOrchestrator:
    """Build a SessionOrchestrator with fully mocked dependencies for session mode.

    Args:
        session_root: The root directory of the session (parent of turn dirs).
        plan_path: The full path to the plan file (e.g., ``session_root / "01" / "plan.md"``).

    Returns:
        A SessionOrchestrator instance wired with MagicMock dependencies
        pre-configured for a successful session execution.
    """
    mock_plan_parser = MagicMock()
    mock_plan_validator = MagicMock()
    mock_fs = MagicMock()
    mock_run_plan = MagicMock()
    mock_user_interactor = MagicMock()
    mock_lifecycle = MagicMock()
    mock_replanner = MagicMock(spec=SessionReplanner)
    mock_context_service = MagicMock()
    mock_config_service = MagicMock()
    mock_llm_client = MagicMock()
    mock_prompt_manager = MagicMock()
    mock_pruning_service = MagicMock()
    mock_session_service = MagicMock()
    mock_session_service.resolve_context_paths.return_value = {
        "Session": [],
        "Turn": [],
    }
    mock_session_service.get_cumulative_cost.return_value = 0.0420

    # Mock the plan
    mock_plan = MagicMock()
    mock_plan.metadata = {"Agent": "developer", "Status": "SUCCESS 🟢"}
    mock_plan.is_session = True
    mock_plan.title = "Test Plan"

    mock_plan_parser.parse.return_value = mock_plan
    mock_plan_validator.validate.return_value = []
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = "# Dummy Plan\n"

    # Mock successful execution
    mock_run_plan.execute.return_value = ExecutionReport(
        run_summary=RunSummary(
            status=RunStatus.SUCCESS,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
        plan_title="Test Plan",
        rationale="Test Rationale",
    )

    # Setup context service to return a mock project context
    project_context = MagicMock()
    project_context.total_tokens = 1000
    project_context.items = []
    mock_context_service.get_context.return_value = project_context

    # Ensure pruning service is a no-op
    mock_pruning_service.prune.side_effect = lambda ctx, **kwargs: ctx

    # Mock config service for model name
    mock_config_service.get_setting.side_effect = lambda key, default=None: (
        "openrouter/deepseek/deepseek-v4-flash:nitro" if key == "llm.model" else default
    )

    # Mock llm client for context window and token counting
    mock_llm_client.get_context_window.return_value = 128000
    mock_llm_client.get_text_token_count.return_value = 100

    # Build orchestrator
    orchestrator = SessionOrchestrator(
        execution_orchestrator=mock_run_plan,
        session_service=mock_session_service,
        file_system_manager=mock_fs,
        plan_validator=mock_plan_validator,
        plan_parser=mock_plan_parser,
        user_interactor=mock_user_interactor,
        lifecycle_manager=mock_lifecycle,
        replanner=mock_replanner,
        context_service=mock_context_service,
        config_service=mock_config_service,
        llm_client=mock_llm_client,
        prompt_manager=mock_prompt_manager,
        pruning_service=mock_pruning_service,
    )

    return orchestrator


def create_session_directory(
    tmp_path: Path, turn_number: str = "01"
) -> tuple[Path, str]:
    """Create a minimal session directory structure for testing.

    Creates ``tmp_path / "test-session-N" / turn_number / plan.md``
    and ``tmp_path / "test-session-N" / meta.yaml``.

    Args:
        tmp_path: A pytest ``tmp_path`` fixture value.
        turn_number: The turn directory name (default "01").

    Returns:
        A tuple of ``(session_root, plan_path)``.
    """
    session_root = tmp_path / f"test-session-{turn_number}"
    turn_dir = session_root / turn_number
    turn_dir.mkdir(parents=True)
    plan_file = turn_dir / "plan.md"
    plan_file.write_text("# Dummy Plan\n", encoding="utf-8")
    meta_file = session_root / "meta.yaml"
    meta_file.write_text("session_name: test-session-1\n", encoding="utf-8")
    plan_path = str(plan_file)
    return session_root, plan_path
