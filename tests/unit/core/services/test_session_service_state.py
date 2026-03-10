import pytest
from unittest.mock import MagicMock
from teddy_executor.core.services.session_service import SessionService
from teddy_executor.core.ports.outbound.session_manager import SessionState


@pytest.fixture
def file_system_manager():
    return MagicMock()


@pytest.fixture
def session_service(file_system_manager):
    return SessionService(file_system_manager)


@pytest.mark.parametrize(
    "plan_exists, report_exists, expected_state",
    [
        (False, False, SessionState.EMPTY),
        (True, False, SessionState.PENDING_PLAN),
        (True, True, SessionState.COMPLETE_TURN),
        (False, True, SessionState.COMPLETE_TURN),  # Edge case: report but no plan
    ],
)
def test_get_session_state_matrix(
    session_service, file_system_manager, plan_exists, report_exists, expected_state
):
    session_name = "test-session"
    latest_turn_dir = ".teddy/sessions/test-session/01"

    file_system_manager.list_directory.return_value = ["01"]

    def path_exists_mock(path):
        if path == f"{latest_turn_dir}/plan.md":
            return plan_exists
        if path == f"{latest_turn_dir}/report.md":
            return report_exists
        return False

    file_system_manager.path_exists.side_effect = path_exists_mock

    state, turn_path = session_service.get_session_state(session_name)

    assert state == expected_state
    assert turn_path == latest_turn_dir
