import pytest

from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from teddy_executor.core.services.plan_validator import PlanValidator
from teddy_executor.core.services.validation_rules.create import CreateActionValidator
from teddy_executor.core.services.validation_rules.edit import EditActionValidator
from teddy_executor.core.services.validation_rules.execute import ExecuteActionValidator
from teddy_executor.core.services.validation_rules.read import ReadActionValidator


@pytest.fixture
def validator(container, mock_fs) -> IPlanValidator:
    """Resolves the PlanValidator from the container with all rules."""
    # Register individual rules; container will inject mock_fs automatically
    container.register(CreateActionValidator)
    container.register(EditActionValidator)
    container.register(ExecuteActionValidator)
    container.register(ReadActionValidator)

    # Register IPlanValidator implementation and its dependencies in one go
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
        rationale="Test",
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
        rationale="Test",
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
        rationale="Test",
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
        rationale="Test",
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
        rationale="Test",
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
        rationale="Test",
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


def test_validate_edit_diff_handling_no_trailing_newline(validator, mock_fs):
    """
    Scenario: Diff lines are always separated by newlines
    Given a FIND block and file content that do NOT end in newlines,
    And they are near matches,
    When validated,
    Then the generated diff must have correct newline separation.
    """
    # Arrange: Note the lack of trailing \n
    file_content = "Line with typo"
    find_block = "Line with typo extra"
    file_path = "test.txt"
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = file_content

    plan = Plan(
        title="Test Newline",
        rationale="Test",
        actions=[
            ActionData(
                type="EDIT",
                params={
                    "path": file_path,
                    "edits": [{"find": find_block, "replace": "fixed"}],
                },
            )
        ],
    )

    # Act
    errors = validator.validate(plan)

    # Assert
    assert len(errors) == 1
    error_msg = errors[0].message

    # Find the diff section
    assert "Closest Match Diff:" in error_msg
    diff_content = error_msg.split("diff\n")[1].split("\n```")[0]

    # Verify that the diff lines are NOT collapsed.
    # ndiff output for this should be:
    # - Line with typo extra
    # ?                ------
    # + Line with typo
    lines = diff_content.splitlines()
    min_expected_lines = 3
    assert len(lines) >= min_expected_lines, (
        f"Expected at least {min_expected_lines} lines in diff, but got: {repr(diff_content)}"
    )
    assert lines[0].startswith("-")
    assert lines[1].startswith("?")
    assert lines[2].startswith("+")


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
        rationale="Test",
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
