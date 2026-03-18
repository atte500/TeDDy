from unittest.mock import MagicMock
import pytest
from teddy_executor.core.services.planning_service import PlanningService


@pytest.fixture
def mock_context_service():
    service = MagicMock()
    service.get_context.return_value = MagicMock(header="header", content="content")
    return service


@pytest.fixture
def mock_llm_client():
    client = MagicMock()
    # Mock structured response
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Generated Plan Content"
    mock_response.choices = [mock_choice]
    mock_response.model = "gpt-4o"

    client.get_completion.return_value = mock_response
    client.get_token_count.return_value = 100
    client.get_completion_cost.return_value = 0.001
    return client


@pytest.fixture
def mock_file_system():
    service = MagicMock()
    # Default meta.yaml content
    service.read_file.return_value = "agent_name: pathfinder\ncumulative_cost: 0.0"
    return service


@pytest.fixture
def mock_config():
    return MagicMock()


def test_generate_plan_uses_model_from_config(
    mock_context_service, mock_llm_client, mock_file_system, mock_config
):
    # Arrange
    # Config defines a specific model for planning
    mock_config.get_setting.return_value = "config-specified-model"

    # We pass the new mock_config to the service
    service = PlanningService(
        context_service=mock_context_service,
        llm_client=mock_llm_client,
        file_system_manager=mock_file_system,
        config_service=mock_config,  # This will trigger a TypeError until __init__ is updated
    )

    # Act
    service.generate_plan(user_message="test", turn_dir="01")

    # Assert
    # Verify that the LLM client was called with the model from config
    mock_llm_client.get_completion.assert_called_once()
    actual_model = mock_llm_client.get_completion.call_args.kwargs["model"]
    assert actual_model == "config-specified-model"


def test_generate_plan_uses_fallback_model_if_not_in_config(
    mock_context_service, mock_llm_client, mock_file_system, mock_config
):
    # Arrange
    # Config returns None for model
    mock_config.get_setting.return_value = None

    service = PlanningService(
        context_service=mock_context_service,
        llm_client=mock_llm_client,
        file_system_manager=mock_file_system,
        config_service=mock_config,
    )

    # Act
    service.generate_plan(user_message="test", turn_dir="01")

    # Assert
    # Should fallback to a safe default (e.g. gpt-4o)
    mock_llm_client.get_completion.assert_called_once()
    actual_model = mock_llm_client.get_completion.call_args.kwargs["model"]
    assert actual_model == "gpt-4o"
