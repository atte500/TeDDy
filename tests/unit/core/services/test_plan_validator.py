from unittest.mock import MagicMock
import pytest
import punq

from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from teddy_executor.core.ports.outbound import IFileSystemManager
from teddy_executor.core.services.plan_validator import PlanValidator
from teddy_executor.core.services.validation_rules.helpers import (
    IActionValidator,
    ValidationError,
)
from teddy_executor.core.services.validation_rules.create import CreateActionValidator
from teddy_executor.core.services.validation_rules.edit import EditActionValidator
from teddy_executor.core.services.validation_rules.execute import ExecuteActionValidator
from teddy_executor.core.services.validation_rules.read import ReadActionValidator


@pytest.fixture
def mock_fs() -> MagicMock:
    return MagicMock(spec=IFileSystemManager)


@pytest.fixture
def validator(container: punq.Container, mock_fs: MagicMock) -> IPlanValidator:
    # Override IFileSystemManager with the mock
    container.register(IFileSystemManager, instance=mock_fs)

    # Re-register sub-validators so they are resolved with the new mock_fs
    container.register(CreateActionValidator)
    container.register(EditActionValidator)
    container.register(ExecuteActionValidator)
    container.register(ReadActionValidator)

    # Re-register IPlanValidator to use the newly resolved validator instances
    container.register(
        IPlanValidator,
        PlanValidator,
        validators=[
            container.resolve(CreateActionValidator),
            container.resolve(EditActionValidator),
            container.resolve(ExecuteActionValidator),
            container.resolve(ReadActionValidator),
        ],
    )
    return container.resolve(IPlanValidator)


def test_validate_edit_action_with_nonexistent_find_block(validator, mock_fs):
    """
    Given a plan with an EDIT action,
    And the target file exists,
    But the FIND block content does not exist in the file,
    When the plan is validated,
    Then a PlanValidationError should be raised.
    """
    # Arrange
    file_path = "app/test.txt"
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = "Hello world"

    plan = Plan(
        title="Test Plan",
        actions=[
            ActionData(
                type="edit",
                params={
                    "path": file_path,
                    "edits": [
                        {"find": "Goodbye world", "replace": "Hello pytest"},
                    ],
                },
                description="Test edit action validation",
            )
        ],
    )

    # Act
    errors = validator.validate(plan)

    # Assert
    assert len(errors) == 1
    assert "The `FIND` block could not be located in the file" in errors[0].message


def test_validate_edit_action_with_nonexistent_file(validator, mock_fs):
    """
    Given a plan with an EDIT action targeting a non-existent file,
    When the plan is validated,
    Then a PlanValidationError should be raised.
    """
    # Arrange
    file_path = "app/nonexistent.txt"
    mock_fs.path_exists.return_value = False

    plan = Plan(
        title="Test Plan",
        actions=[
            ActionData(
                type="edit",
                params={
                    "path": file_path,
                    "edits": [{"find": "anything", "replace": "doesn't matter"}],
                },
                description="Test edit on non-existent file",
            )
        ],
    )

    # Act
    errors = validator.validate(plan)

    # Assert
    assert len(errors) == 1
    assert "File to edit does not exist" in errors[0].message


def test_validate_edit_action_with_valid_find_block(validator, mock_fs):
    """
    Given a plan with an EDIT action,
    And the FIND block content exists in the file,
    When the plan is validated,
    Then no exception should be raised.
    """
    # Arrange
    file_path = "app/test.txt"
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = "Hello world"

    plan = Plan(
        title="Test Plan",
        actions=[
            ActionData(
                type="edit",
                params={
                    "path": file_path,
                    "edits": [{"find": "Hello world", "replace": "Hello pytest"}],
                },
                description="Test edit action validation",
            )
        ],
    )

    # Act
    errors = validator.validate(plan)

    # Assert
    assert len(errors) == 0, f"Expected no errors, but got: {errors}"


def test_validate_create_fails_if_file_exists(validator, mock_fs):
    """
    Given a CREATE action for a file that exists,
    When validated,
    Then it should return an error.
    """
    mock_fs.path_exists.return_value = True

    plan = Plan(
        title="Test",
        actions=[
            ActionData(type="CREATE", params={"path": "existing.txt", "content": "foo"})
        ],
    )

    errors = validator.validate(plan)

    assert len(errors) == 1
    assert "File already exists" in errors[0].message
    assert errors[0].file_path == "existing.txt"


def test_validate_edit_fails_if_find_block_not_unique(validator, mock_fs):
    """
    Given an EDIT action where the FIND block appears multiple times in the file,
    When validated,
    Then it should return an error.
    """
    content = "def foo():\n    pass\n\ndef foo():\n    pass"
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = content

    find_content = "def foo():\n    pass"
    plan = Plan(
        title="Test",
        actions=[
            ActionData(
                type="EDIT",
                params={
                    "path": "source.py",
                    "edits": [{"find": find_content, "replace": "bar"}],
                },
            )
        ],
    )

    errors = validator.validate(plan)

    assert len(errors) == 1
    assert "Found 2 matches" in errors[0].message


def test_validate_execute_action_fails_for_multiline_commands():
    """
    Given an EXECUTE action with multiple commands,
    When validated,
    Then it should return an error.
    """
    plan = Plan(
        title="Test",
        actions=[
            ActionData(
                type="EXECUTE",
                params={"command": "echo 'hello'\necho 'world'"},
            )
        ],
    )

    validator = PlanValidator(MagicMock(spec=IFileSystemManager))
    errors = validator.validate(plan)

    assert len(errors) == 1
    assert "EXECUTE action must contain exactly one command" in errors[0].message


def test_validate_execute_action_fails_for_chained_commands():
    """
    Given an EXECUTE action with chained commands (&&),
    When validated,
    Then it should return an error.
    """
    plan = Plan(
        title="Test",
        actions=[
            ActionData(
                type="EXECUTE",
                params={"command": "echo 'hello' && echo 'world'"},
            )
        ],
    )

    validator = PlanValidator(MagicMock(spec=IFileSystemManager))
    errors = validator.validate(plan)

    assert len(errors) == 1
    assert "Command chaining with '&&' is not allowed" in errors[0].message


def test_validate_execute_succeeds_for_single_command_with_line_continuations():
    """
    Given an EXECUTE action with a single command spanning multiple lines using '\\',
    When validated,
    Then it should not return any errors.
    """
    command = (
        "echo 'this is a very long line' \\\n--and-it 'continues on the next line'"
    )
    plan = Plan(
        title="Test",
        actions=[ActionData(type="EXECUTE", params={"command": command})],
    )

    validator = PlanValidator(MagicMock(spec=IFileSystemManager))
    errors = validator.validate(plan)

    assert len(errors) == 0, (
        f"Expected no errors for line continuation, but got: {errors}"
    )


def test_validate_execute_succeeds_for_single_command_with_multiline_argument():
    """
    Given a single command with a multiline string argument,
    When validated,
    Then it should not return an error.
    """
    command = "git commit -m 'Subject\n\nThis is the body.'"
    plan = Plan(
        title="Test",
        actions=[ActionData(type="EXECUTE", params={"command": command})],
    )

    validator = PlanValidator(MagicMock(spec=IFileSystemManager))
    errors = validator.validate(plan)

    assert len(errors) == 0, (
        f"Expected no errors for multiline argument, but got: {errors}"
    )


def test_validate_execute_succeeds_with_ampersands_in_quoted_string():
    """
    Given an EXECUTE action with '&&' inside a quoted string,
    When validated,
    Then it should not return an error.
    """
    command = "echo 'hello && world'"
    plan = Plan(
        title="Test",
        actions=[ActionData(type="EXECUTE", params={"command": command})],
    )

    validator = PlanValidator(MagicMock(spec=IFileSystemManager))
    errors = validator.validate(plan)

    assert len(errors) == 0, (
        f"Expected no errors for quoted ampersands, but got: {errors}"
    )


def test_validate_execute_action_succeeds_for_single_command_with_directives():
    """
    Given an EXECUTE action with a single command and directives,
    When validated,
    Then it should not return any errors.
    """
    command = "cd /tmp\nexport FOO=bar\nls -l"
    plan = Plan(
        title="Test",
        actions=[ActionData(type="EXECUTE", params={"command": command})],
    )

    validator = PlanValidator(MagicMock(spec=IFileSystemManager))
    errors = validator.validate(plan)

    assert len(errors) == 0, f"Expected no errors, but got: {errors}"


def test_validate_execute_fails_with_unsafe_cwd_traversal(validator):
    """
    Given an EXECUTE action where `cwd` attempts to traverse outside the project root,
    When validated,
    Then it should return an error.
    """
    plan = Plan(
        title="Test",
        actions=[
            ActionData(
                type="EXECUTE",
                params={"command": "echo 'test'", "cwd": "../unsafe"},
            )
        ],
    )
    errors = validator.validate(plan)

    assert len(errors) == 1
    assert "is outside the project directory" in errors[0].message
    assert errors[0].file_path is None  # Not file-specific error


def test_validate_execute_fails_with_absolute_cwd(validator):
    """
    Given an EXECUTE action where `cwd` is an absolute path,
    When validated,
    Then it should return an error.
    """
    import os

    absolute_cwd = "/etc/passwd" if os.name != "nt" else "C:\\Windows"

    plan = Plan(
        title="Test",
        actions=[
            ActionData(
                type="EXECUTE",
                params={"command": "echo 'test'", "cwd": absolute_cwd},
            )
        ],
    )
    errors = validator.validate(plan)

    assert len(errors) == 1
    assert "is an absolute path and is not allowed" in errors[0].message


def test_validate_edit_reports_multiple_failures(validator, mock_fs):
    """
    Given an EDIT action with multiple FIND blocks that do not match,
    When validated,
    Then all errors should be reported.
    """
    file_path = "test.txt"
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = "Some content"

    plan = Plan(
        title="Test",
        actions=[
            ActionData(
                type="EDIT",
                params={
                    "path": file_path,
                    "edits": [
                        {"find": "Bad1", "replace": "Good1"},
                        {"find": "Bad2", "replace": "Good2"},
                    ],
                },
            )
        ],
    )

    errors = validator.validate(plan)

    expected_error_count = 2
    assert len(errors) == expected_error_count
    assert "Bad1" in errors[0].message
    assert "Bad2" in errors[1].message


def test_validate_edit_provides_diff_on_mismatch(validator, mock_fs):
    """
    Given an EDIT action with a near-match FIND block,
    When validated,
    Then the error message should contain a diff.
    """
    file_path = "test.txt"
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = "This is the original content"

    plan = Plan(
        title="Test",
        actions=[
            ActionData(
                type="EDIT",
                params={
                    "path": file_path,
                    "edits": [
                        {"find": "This is the orignal content", "replace": "New"},
                    ],
                },
            )
        ],
    )

    errors = validator.validate(plan)

    assert len(errors) == 1
    assert "- This is the orignal content" in errors[0].message
    assert "+ This is the original content" in errors[0].message
    assert "?" in errors[0].message


def test_validate_edit_fails_if_find_and_replace_identical(validator, mock_fs):
    """
    Given an EDIT action where FIND and REPLACE are identical,
    When validated,
    Then it should return an error.
    """
    mock_fs.path_exists.return_value = True

    content = "same content"
    plan = Plan(
        title="Test",
        actions=[
            ActionData(
                type="EDIT",
                params={
                    "path": "source.py",
                    "edits": [{"find": content, "replace": content}],
                },
            )
        ],
    )

    errors = validator.validate(plan)

    assert len(errors) == 1
    assert "FIND and REPLACE blocks are identical" in errors[0].message


def test_plan_validator_uses_injected_validators(validator):
    # Arrange
    mock_validator = MagicMock(spec=IActionValidator)
    mock_validator.can_validate.return_value = True
    mock_validator.validate.return_value = [ValidationError(message="Mock Error")]

    plan = Plan(title="Test Plan", actions=[ActionData(type="test_action", params={})])

    # Injected via constructor in the fixture setup if we wanted, but we can also
    # just create a new one here to test the specific behavior.
    v = PlanValidator(file_system_manager=MagicMock(), validators=[mock_validator])

    # Act
    errors = v.validate(plan)

    # Assert
    assert len(errors) == 1
    assert errors[0].message == "Mock Error"
    mock_validator.can_validate.assert_called_once_with("test_action")
    mock_validator.validate.assert_called_once()


def test_read_action_validator_reports_error_if_file_missing(validator, mock_fs):
    # Arrange
    mock_fs.path_exists.return_value = False

    plan = Plan(
        title="Test",
        actions=[ActionData(type="READ", params={"resource": "nonexistent.txt"})],
    )

    # Act
    errors = validator.validate(plan)

    # Assert
    assert len(errors) == 1
    assert "File to read does not exist" in errors[0].message
    assert errors[0].file_path == "nonexistent.txt"


def test_validate_fails_for_unknown_action_type():
    """
    Given a plan with an unknown action type,
    When validated,
    Then it should return an error.
    """
    plan = Plan(
        title="Test",
        actions=[
            ActionData(type="EXECUTE", params={"command": "echo 'valid'"}),
            ActionData(type="UNKNOWN_ACTION", params={}),
        ],
    )

    validator = PlanValidator(MagicMock(spec=IFileSystemManager))
    errors = validator.validate(plan)

    assert len(errors) == 1
    assert "Unknown action type: UNKNOWN_ACTION" in errors[0].message
