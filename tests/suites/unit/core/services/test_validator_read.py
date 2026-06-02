from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator


def test_read_action_validator_reports_error_if_file_missing(container, mock_fs):
    # Arrange
    validator = container.resolve(IPlanValidator)
    mock_fs.path_exists.return_value = False
    # Arrange
    mock_fs.path_exists.return_value = False

    plan = Plan(
        title="Test",
        rationale="Test",
        actions=[ActionData(type="READ", params={"resource": "nonexistent.txt"})],
    )

    # Act
    errors = validator.validate(plan)

    # Assert
    assert len(errors) == 1
    assert "File to read does not exist" in errors[0].message
    assert errors[0].file_path == "nonexistent.txt"


def test_read_action_validator_allows_file_already_in_context(container, mock_fs):
    """
    Unit test: READ should be allowed even if the file is already in context
    per the relaxed validation requirements.
    """
    # Arrange
    validator = container.resolve(IPlanValidator)
    mock_fs.path_exists.return_value = True

    plan = Plan(
        title="Test",
        rationale="Test",
        actions=[ActionData(type="READ", params={"resource": "README.md"})],
    )
    # context_paths must be a Dict[str, List[str]]
    context_paths = {"Session": ["README.md"], "Turn": []}

    # Act
    errors = validator.validate(plan, context_paths=context_paths)

    # Assert
    # Current behavior: returns 1 error "README.md is already in context"
    # Target behavior: returns 0 errors
    assert len(errors) == 0
