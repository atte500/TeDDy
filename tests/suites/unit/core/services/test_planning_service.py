import pytest
from teddy_executor.core.services.planning_service import PlanningService


@pytest.fixture
def service(container, mock_fs, mock_config, mock_llm_client, mock_context_service):
    # Ensure all dependencies are registered in the container before resolution
    container.register(PlanningService)
    return container.resolve(PlanningService)


def test_generate_plan_uses_model_from_config(
    service, mock_llm_client, mock_config, mock_fs
):
    # Arrange
    mock_config.get_setting.return_value = "config-specified-model"
    mock_fs.path_exists.return_value = False  # No meta.yaml or agent.xml

    # Act
    service.generate_plan(user_message="test", turn_dir="01")

    # Assert
    mock_llm_client.get_completion.assert_called_once()
    actual_model = mock_llm_client.get_completion.call_args.kwargs["model"]
    assert actual_model == "config-specified-model"


def test_generate_plan_uses_fallback_model_if_not_in_config(
    service, mock_llm_client, mock_config, mock_fs
):
    # Arrange
    mock_config.get_setting.return_value = None
    mock_fs.path_exists.return_value = False

    # Act
    service.generate_plan(user_message="test", turn_dir="01")

    # Assert
    mock_llm_client.get_completion.assert_called_once()
    actual_model = mock_llm_client.get_completion.call_args.kwargs["model"]
    assert actual_model == "gpt-4o"
