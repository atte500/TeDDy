from unittest.mock import Mock
import pytest
from teddy_executor.core.services.session_orchestrator import SessionOrchestrator
from teddy_executor.core.services.session_replanner import SessionReplanner
from teddy_executor.core.ports.outbound.session_manager import SessionState


@pytest.fixture
def mocks():
    fs = Mock()
    fs.read_file.return_value = (
        "agent_name: pathfinder\ncumulative_cost: 0.0\nturn_cost: 0.0"
    )

    ps = Mock()
    ps.generate_plan.return_value = ("path/to/plan.md", 0.0)

    ss = Mock()
    ss.get_session_state.return_value = (SessionState.EMPTY, "session/01")

    planning_service = ps
    user_interactor = Mock()
    return {
        "execution_orchestrator": Mock(),
        "session_service": ss,
        "file_system_manager": fs,
        "plan_validator": Mock(),
        "plan_parser": Mock(),
        "user_interactor": user_interactor,
        "lifecycle_manager": Mock(),
        "replanner": SessionReplanner(fs, planning_service),
        "llm_client": Mock(),
    }


def test_trigger_new_plan_uses_ask_question(mocks):
    # Arrange
    mocks["context_service"] = Mock()
    mock_config = Mock()
    mock_config.get_setting.side_effect = lambda key, default=None: default
    mocks["config_service"] = mock_config
    mocks["prompt_manager"] = Mock()
    orchestrator = SessionOrchestrator(**mocks)

    # Act
    orchestrator.resume("session_name")

    # Assert
    # Verify delegation to lifecycle manager
    mocks["lifecycle_manager"].resume.assert_called_once_with(
        "session_name", orchestrator, True, project_context=None
    )
