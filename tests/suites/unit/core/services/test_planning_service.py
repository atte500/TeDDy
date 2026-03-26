import pytest
from teddy_executor.core.domain.models import ProjectContext
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


def test_generate_plan_writes_standardized_input_md(
    service, mock_context_service, mock_fs, mock_llm_client
):
    # Arrange
    mock_context_service.get_context.return_value = ProjectContext(
        header="Expected Header",
        content="Expected Content",
        scoped_paths={},
        git_status="",
    )
    mock_fs.path_exists.return_value = False

    # Act
    service.generate_plan(user_message="test", turn_dir="turns/01")

    # Assert
    # Verify input.md contains the standardized context (Deliverable: input.md artifact)
    mock_fs.write_file.assert_any_call(
        "turns/01/input.md", "Expected Header\nExpected Content"
    )
