from unittest.mock import MagicMock
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator
from teddy_executor.core.domain.models import Plan


def test_execute_persists_manual_plan_content_to_temp_file():
    """
    Verifies that when plan_content is provided without a plan_path,
    the orchestrator persists it to a temporary file.
    """
    # Setup
    mock_parser = MagicMock()
    mock_validator = MagicMock()
    mock_executor = MagicMock()
    mock_executor.confirm_and_dispatch.return_value = (MagicMock(), "")
    mock_fs = MagicMock()

    # Mock validator to pass
    mock_validator.validate.return_value = []

    # Mock parser to return a plan
    mock_action = MagicMock()
    mock_action.selected = True
    mock_plan = Plan(
        title="Test Plan", rationale="Test", metadata={}, actions=[mock_action]
    )
    mock_parser.parse.return_value = mock_plan

    orchestrator = ExecutionOrchestrator(
        plan_parser=mock_parser,
        plan_validator=mock_validator,
        action_executor=mock_executor,
        file_system_manager=mock_fs,
    )

    plan_content = "# Test Plan\n## Rationale\n..."

    # Act
    orchestrator.execute(plan_content=plan_content, interactive=False)

    # Assert
    # We expect the orchestrator to have written the content to a file
    # since no plan_path was provided.
    assert mock_fs.write_file.called, "Should have persisted plan_content to a file"
    # And the plan_path passed to the parser should be the new temp path
    called_path = mock_parser.parse.call_args[1].get("plan_path")
    assert called_path is not None
    assert "manual_plan" in called_path
