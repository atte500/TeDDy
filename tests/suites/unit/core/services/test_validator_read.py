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
