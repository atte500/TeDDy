import json
import pytest
import yaml
from teddy_executor.core.services.planning_service import PlanningService


@pytest.fixture
def service(container, mock_fs, mock_config, mock_llm_client, mock_context_service):
    # Ensure all dependencies are registered in the container before resolution
    container.register(PlanningService)
    return container.resolve(PlanningService)


def test_generate_plan_logs_token_usage_if_available(
    service, mock_llm_client, mock_config, capsys, mock_fs
):
    # Arrange
    mock_config.get_setting.return_value = "gpt-4"
    mock_llm_client.get_completion.return_value = "plan content"
    mock_llm_client.get_token_count.return_value = 100
    mock_llm_client.get_completion_cost.return_value = 0.015
    mock_fs.path_exists.return_value = False

    # Act
    service.generate_plan(user_message="test", turn_dir="01")

    # Assert
    captured = capsys.readouterr()
    assert "Tokens: 100" in captured.out
    assert "Cost: $0.0150" in captured.out


def test_generate_plan_handles_zero_usage_gracefully(
    service, mock_llm_client, mock_config, capsys, mock_fs
):
    # Arrange
    mock_config.get_setting.return_value = "gpt-4"
    mock_llm_client.get_completion.return_value = "plan content"
    mock_llm_client.get_token_count.return_value = 0
    mock_llm_client.get_completion_cost.return_value = 0.0
    mock_fs.path_exists.return_value = False

    # Act
    service.generate_plan(user_message="test", turn_dir="01")

    # Assert
    captured = capsys.readouterr()
    assert "Tokens: 0" in captured.out
    assert "Cost: $0.0000" in captured.out


def test_generate_plan_logs_input_and_uses_agent_prompt(
    service, mock_fs, mock_llm_client, mock_config
):
    # Arrange
    turn_dir = "session/01"
    mock_fs.read_file.side_effect = [
        yaml.dump({"agent_name": "pathfinder", "turn_id": "01"}),  # meta.yaml
        "<prompt>Pathfinder prompt</prompt>",  # pathfinder.xml
    ]
    mock_fs.path_exists.return_value = True

    # Act
    service.generate_plan("Hello", turn_dir)

    # Assert
    # 1. Verify pathfinder.xml was read
    from pathlib import Path

    mock_fs.read_file.assert_any_call(str(Path("session/01/pathfinder.xml")))

    # 2. Verify input.log was written
    log_call = [
        call for call in mock_fs.write_file.call_args_list if "input.log" in call[0][0]
    ]
    assert len(log_call) == 1
    log_content = json.loads(log_call[0][0][1])
    assert log_content[0]["role"] == "system"
    assert log_content[0]["content"] == "<prompt>Pathfinder prompt</prompt>"
