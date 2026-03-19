import pytest
from teddy_executor.core.ports.outbound.session_manager import (
    ISessionManager,
    SessionState,
)


@pytest.mark.parametrize(
    "plan_exists, report_exists, expected_state",
    [
        (False, False, SessionState.EMPTY),
        (True, False, SessionState.PENDING_PLAN),
        (True, True, SessionState.COMPLETE_TURN),
        (False, True, SessionState.COMPLETE_TURN),  # Edge case: report but no plan
    ],
)
def test_get_session_state_matrix(env, plan_exists, report_exists, expected_state):
    """
    Tests the get_session_state matrix using a mocked filesystem.
    """
    # Arrange
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()

    session_name = "test-session"
    latest_turn_dir = f".teddy/sessions/{session_name}/01"

    mock_fs.list_directory.return_value = ["01"]

    def path_exists_mock(path):
        if path == f"{latest_turn_dir}/plan.md":
            return plan_exists
        if path == f"{latest_turn_dir}/report.md":
            return report_exists
        return False

    mock_fs.path_exists.side_effect = path_exists_mock

    # Act
    state, turn_path = service.get_session_state(session_name)

    # Assert
    assert state == expected_state
    assert turn_path == latest_turn_dir
