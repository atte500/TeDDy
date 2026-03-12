from unittest.mock import MagicMock
import pytest
import yaml
from teddy_executor.core.services.session_service import SessionService


@pytest.fixture
def mock_fs():
    return MagicMock()


@pytest.fixture
def service(mock_fs):
    return SessionService(mock_fs)


def test_transition_to_next_turn_persists_cumulative_cost(service, mock_fs):
    plan_path = "session/01/plan.md"
    # mock_fs setup: meta.yaml, turn.context, pathfinder.xml (for copying)
    mock_fs.read_file.side_effect = [
        yaml.dump(
            {"turn_id": "01", "cumulative_cost": 0.01, "agent_name": "pathfinder"}
        ),  # current meta.yaml
        "",  # current turn.context
        "<prompt/>",  # pathfinder.xml
    ]
    mock_fs.path_exists.return_value = True

    service.transition_to_next_turn(plan_path, turn_cost=0.02)

    # Verify next meta.yaml content
    write_calls = [
        call
        for call in mock_fs.write_file.call_args_list
        if "02/meta.yaml" in call[0][0]
    ]
    assert len(write_calls) == 1
    next_meta = yaml.safe_load(write_calls[0][0][1])
    assert next_meta["cumulative_cost"] == 0.03  # noqa: PLR2004
