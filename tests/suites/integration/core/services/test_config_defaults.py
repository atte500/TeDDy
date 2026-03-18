import pytest
from teddy_executor.core.domain.models.plan import (
    ActionData,
    Plan,
    DEFAULT_SIMILARITY_THRESHOLD,
)
from teddy_executor.core.domain.models.execution_report import RunStatus
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator
from teddy_executor.core.ports.outbound import IConfigService
from teddy_executor.adapters.outbound.yaml_config_adapter import YamlConfigAdapter


@pytest.fixture
def orchestrator_no_config(container):
    """Provides an ExecutionOrchestrator configured with a non-existent config file."""
    # Register a YamlConfigAdapter pointing to a non-existent path
    container.register(
        IConfigService,
        factory=lambda: YamlConfigAdapter(config_path="non_existent.yaml"),
    )
    container.register(IRunPlanUseCase, ExecutionOrchestrator)
    return container.resolve(IRunPlanUseCase)


def test_execute_action_uses_hardcoded_timeout_fallback_when_config_is_missing(
    orchestrator_no_config, mock_shell
):
    """
    Given a Plan with an EXECUTE action and a missing .teddy/config.yaml,
    When the plan is executed,
    Then the ActionFactory should still inject the hardcoded default timeout of 30.0.
    """
    # Arrange
    plan = Plan(
        title="Test Default Timeout",
        rationale="Verify fallback logic",
        actions=[
            ActionData(
                type="EXECUTE",
                params={"command": "echo hello"},
            )
        ],
    )
    original_execute = mock_shell.execute
    original_execute.return_value = {"stdout": "hello", "return_code": 0}

    # Act
    report = orchestrator_no_config.execute(plan=plan, interactive=False)

    # Assert
    assert report.run_summary.status == RunStatus.SUCCESS
    # This is the failing expectation: it should be 30.0 even without config
    original_execute.assert_called_once_with(command="echo hello", timeout=30.0)


def test_edit_action_uses_hardcoded_similarity_fallback_when_config_is_missing(
    container, mock_fs
):
    """
    Given a Plan with an EDIT action and a missing .teddy/config.yaml,
    When the plan is executed,
    Then the ActionFactory should still inject the hardcoded default similarity threshold of 0.95.
    """
    # Arrange
    # Force the container to use THIS mock for everything resolved AFTER this point
    container.register(
        IConfigService,
        factory=lambda: YamlConfigAdapter(config_path="non_existent.yaml"),
    )
    container.register(IRunPlanUseCase, ExecutionOrchestrator)
    orchestrator_no_config = container.resolve(IRunPlanUseCase)

    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = "original content"

    plan = Plan(
        title="Test Default Similarity",
        rationale="Verify fallback logic",
        actions=[
            ActionData(
                type="EDIT",
                params={
                    "path": "test.txt",
                    "edits": [{"find": "original", "replace": "new"}],
                },
            )
        ],
    )

    # Act
    report = orchestrator_no_config.execute(plan=plan, interactive=False)

    # Assert
    assert report.run_summary.status == RunStatus.SUCCESS
    # We expect similarity_threshold to be injected as the default
    mock_fs.edit_file.assert_called_once()
    kwargs = mock_fs.edit_file.call_args.kwargs
    assert kwargs.get("similarity_threshold") == DEFAULT_SIMILARITY_THRESHOLD
