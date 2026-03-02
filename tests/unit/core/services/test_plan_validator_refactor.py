from unittest.mock import MagicMock
from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.services.plan_validator import PlanValidator
from teddy_executor.core.services.validation_rules.helpers import (
    IActionValidator,
    ValidationError,
)
from teddy_executor.core.services.validation_rules.create import CreateActionValidator
from teddy_executor.core.services.validation_rules.edit import EditActionValidator
from teddy_executor.core.services.validation_rules.read import ReadActionValidator
from teddy_executor.core.services.validation_rules.execute import ExecuteActionValidator


def test_plan_validator_uses_injected_validators():
    # Arrange
    mock_validator = MagicMock(spec=IActionValidator)
    mock_validator.can_validate.return_value = True
    mock_validator.validate.return_value = [ValidationError(message="Mock Error")]

    # We want to support passing a list of validators to the constructor
    # Current implementation only takes file_system_manager
    plan = Plan(title="Test Plan", actions=[ActionData(type="test_action", params={})])

    # This will fail because the constructor doesn't accept 'validators' yet
    validator = PlanValidator(
        file_system_manager=MagicMock(), validators=[mock_validator]
    )

    # Act
    errors = validator.validate(plan)

    # Assert
    assert len(errors) == 1
    assert errors[0].message == "Mock Error"
    mock_validator.can_validate.assert_called_once_with("test_action")
    mock_validator.validate.assert_called_once()


def test_create_action_validator_reports_error_if_file_exists():
    # Arrange
    mock_fs = MagicMock()
    mock_fs.path_exists.return_value = True

    validator = CreateActionValidator(file_system_manager=mock_fs)
    action = ActionData(type="CREATE", params={"path": "existing.txt"})

    # Act
    errors = validator.validate(action)

    # Assert
    assert len(errors) == 1
    assert "File already exists" in errors[0].message
    assert errors[0].file_path == "existing.txt"


def test_edit_action_validator_reports_error_if_find_block_missing():
    # Arrange
    mock_fs = MagicMock()
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = "line 1\nline 2"

    validator = EditActionValidator(file_system_manager=mock_fs)
    action = ActionData(
        type="EDIT",
        params={"path": "test.txt", "edits": [{"find": "missing", "replace": "found"}]},
    )

    # Act
    errors = validator.validate(action)

    # Assert
    assert len(errors) == 1
    assert "The `FIND` block could not be located" in errors[0].message
    assert errors[0].file_path == "test.txt"


def test_read_action_validator_reports_error_if_file_missing():
    # Arrange
    mock_fs = MagicMock()
    mock_fs.path_exists.return_value = False

    validator = ReadActionValidator(file_system_manager=mock_fs)
    action = ActionData(type="READ", params={"resource": "nonexistent.txt"})

    # Act
    errors = validator.validate(action)

    # Assert
    assert len(errors) == 1
    assert "File to read does not exist" in errors[0].message
    assert errors[0].file_path == "nonexistent.txt"


def test_execute_action_validator_reports_error_for_multiline_command():
    # Arrange
    validator = ExecuteActionValidator()
    action = ActionData(type="EXECUTE", params={"command": "echo 1\necho 2"})

    # Act
    errors = validator.validate(action)

    # Assert
    assert len(errors) == 1
    assert "must contain exactly one command" in errors[0].message
