import yaml
from teddy_executor.core.services.planning_service import PlanningService
from teddy_executor.core.ports.outbound import (
    ILlmClient,
    IConfigService,
    IFileSystemManager,
)


def test_generate_plan_logs_token_usage_if_available(env, mock_prompt_manager):
    """Verifies that telemetry is logged via interactor."""
    # Arrange
    service = env.get_service(PlanningService)
    mock_config = env.get_service(IConfigService)
    mock_llm_client = env.get_service(ILlmClient)
    mock_fs = env.get_service(IFileSystemManager)

    mock_config.get_setting.return_value = "gpt-4"
    mock_llm_client.get_completion.return_value = "plan content"
    mock_llm_client.get_token_count.return_value = 100
    mock_llm_client.get_completion_cost.return_value = 0.015
    mock_fs.path_exists.return_value = False

    # Act
    service.generate_plan(user_message="test", turn_dir="01")

    # Assert
    mock_prompt_manager.log_telemetry.assert_called_once_with(100, 0.015)


def test_generate_plan_handles_zero_usage_gracefully(env, mock_prompt_manager):
    """Verifies graceful handling of zero telemetry."""
    # Arrange
    service = env.get_service(PlanningService)
    mock_config = env.get_service(IConfigService)
    mock_llm_client = env.get_service(ILlmClient)
    mock_fs = env.get_service(IFileSystemManager)

    mock_config.get_setting.return_value = "gpt-4"
    mock_llm_client.get_completion.return_value = "plan content"
    mock_llm_client.get_token_count.return_value = 0
    mock_llm_client.get_completion_cost.return_value = 0.0
    mock_fs.path_exists.return_value = False

    # Act
    service.generate_plan(user_message="test", turn_dir="01")

    # Assert
    mock_prompt_manager.log_telemetry.assert_called_once_with(0, 0.0)


def test_generate_plan_logs_input_and_uses_agent_prompt(env, mock_prompt_manager):
    """Verifies that the correct prompt file is read and logged."""
    # Arrange
    service = env.get_service(PlanningService)
    mock_fs = env.get_service(IFileSystemManager)
    turn_dir = "session/01"

    mock_fs.read_file.side_effect = [
        yaml.dump({"agent_name": "pathfinder", "turn_id": "01"}),  # meta.yaml
        "<prompt>Pathfinder prompt</prompt>",  # pathfinder.xml
    ]
    mock_fs.path_exists.return_value = True

    # Act
    service.generate_plan("Hello", turn_dir)

    # Assert
    from pathlib import Path

    # Verify PlanningService delegated message resolution and metadata lookup
    mock_prompt_manager.resolve_message.assert_called_once_with("Hello", Path(turn_dir))
    mock_prompt_manager.resolve_agent_metadata.assert_called_once_with(Path(turn_dir))
