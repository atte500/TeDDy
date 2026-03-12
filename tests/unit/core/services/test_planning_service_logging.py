import json
from unittest.mock import MagicMock
import pytest
import yaml
from teddy_executor.core.services.planning_service import PlanningService


@pytest.fixture
def mock_context_service():
    mock = MagicMock()
    mock.get_context.return_value = MagicMock(header="Header", content="Content")
    return mock


@pytest.fixture
def mock_llm_client():
    mock = MagicMock()

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "# Plan"
    mock_response.choices = [mock_choice]
    mock_response.model = "test-model"

    mock.get_completion.return_value = mock_response
    mock.get_token_count.return_value = 100
    mock.get_completion_cost.return_value = 0.01
    return mock


@pytest.fixture
def mock_fs():
    return MagicMock()


@pytest.fixture
def mock_config():
    mock = MagicMock()
    mock.get_setting.return_value = "gpt-4"
    return mock


@pytest.fixture
def service(mock_context_service, mock_llm_client, mock_fs, mock_config):
    return PlanningService(mock_context_service, mock_llm_client, mock_fs, mock_config)


def test_generate_plan_logs_input_and_uses_agent_prompt(
    service, mock_fs, mock_llm_client
):
    turn_dir = "session/01"
    mock_fs.read_file.side_effect = [
        yaml.dump({"agent_name": "pathfinder", "turn_id": "01"}),  # meta.yaml
        "<prompt>Pathfinder prompt</prompt>",  # pathfinder.xml
    ]

    service.generate_plan("Hello", turn_dir)

    # 1. Verify pathfinder.xml was read
    mock_fs.read_file.assert_any_call("session/01/pathfinder.xml")

    # 2. Verify input.log was written
    # We find the call to write_file for input.log
    log_call = [
        call for call in mock_fs.write_file.call_args_list if "input.log" in call[0][0]
    ]
    assert len(log_call) == 1
    log_content = json.loads(log_call[0][0][1])
    assert log_content[0]["role"] == "system"
    assert log_content[0]["content"] == "<prompt>Pathfinder prompt</prompt>"
