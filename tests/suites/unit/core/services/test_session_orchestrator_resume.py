from unittest.mock import MagicMock
import pytest
from teddy_executor.core.services.session_orchestrator import SessionOrchestrator


@pytest.fixture
def mock_lifecycle_manager():
    from teddy_executor.core.services.session_lifecycle_manager import (
        SessionLifecycleManager,
    )

    return MagicMock(spec=SessionLifecycleManager)


@pytest.fixture
def orchestrator(  # noqa: PLR0913
    mock_run_plan,
    mock_session_manager,
    mock_fs,
    mock_plan_validator,
    mock_plan_parser,
    mock_user_interactor,
    mock_lifecycle_manager,
):
    from teddy_executor.core.services.session_replanner import SessionReplanner

    # Manual instantiation for unit tests ensures direct control over collaborators
    replanner = SessionReplanner(
        file_system_manager=mock_fs,
        planning_service=MagicMock(),
    )

    mock_config = MagicMock()
    mock_config.get_setting.side_effect = lambda key, default=None: default

    mock_prompt_manager = MagicMock()
    mock_prompt_manager.fetch_system_prompt.return_value = "mock prompt"
    mock_llm_client = MagicMock()
    mock_llm_client.get_text_token_count.return_value = 100

    return SessionOrchestrator(
        execution_orchestrator=mock_run_plan,
        session_service=mock_session_manager,
        file_system_manager=mock_fs,
        plan_validator=mock_plan_validator,
        plan_parser=mock_plan_parser,
        user_interactor=mock_user_interactor,
        lifecycle_manager=mock_lifecycle_manager,
        replanner=replanner,
        context_service=MagicMock(),
        config_service=mock_config,
        llm_client=mock_llm_client,
        prompt_manager=mock_prompt_manager,
    )


def test_resume_delegates_to_lifecycle_manager(orchestrator, mock_lifecycle_manager):
    """
    SessionOrchestrator.resume should delegate to SessionLifecycleManager.resume.
    """
    # Arrange
    session_name = "test-session"

    # Act
    orchestrator.resume(session_name)

    # Assert
    mock_lifecycle_manager.resume.assert_called_once_with(
        session_name, orchestrator, True, None, project_context=None
    )
