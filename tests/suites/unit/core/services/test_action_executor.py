import pytest
from unittest.mock import MagicMock
from teddy_executor.core.domain.models import ActionData, ActionStatus
from teddy_executor.core.services.action_executor import ActionExecutor


@pytest.fixture
def mock_deps():
    return {
        "action_dispatcher": MagicMock(),
        "user_interactor": MagicMock(),
        "file_system_manager": MagicMock(),
        "edit_simulator": MagicMock(),
        "config_service": MagicMock(),
    }


@pytest.fixture
def executor(mock_deps):
    return ActionExecutor(**mock_deps)


@pytest.mark.parametrize("terminal_type", ["PROMPT", "INVOKE", "RETURN"])
def test_confirm_and_dispatch_skips_terminal_action_in_multi_action_plan_when_not_interactive(
    executor, terminal_type
):
    # Arrange
    action = ActionData(type=terminal_type, params={}, description="test")

    # Act
    # interactive=False represents non-TUI/bulk execution
    log, message = executor.confirm_and_dispatch(
        action, interactive=False, total_actions=2
    )

    # Assert
    assert log.status == ActionStatus.SKIPPED
    assert (
        log.details
        == "Action skipped to ensure state isolation; must be executed as a single-action plan."
    )
    assert message == ""


def test_confirm_and_dispatch_allows_terminal_action_in_single_action_plan_when_not_interactive(
    executor, mock_deps, terminal_type="PROMPT"
):
    # Arrange
    action = ActionData(type=terminal_type, params={}, description="test")
    mock_deps["action_dispatcher"].dispatch_and_execute.return_value = MagicMock(
        status=ActionStatus.SUCCESS
    )

    # Act
    log, message = executor.confirm_and_dispatch(
        action, interactive=False, total_actions=1
    )

    # Assert
    assert log.status == ActionStatus.SUCCESS
    assert message == ""
