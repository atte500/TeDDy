import pytest
from pathlib import Path

from teddy_executor.core.domain.models.plan import Plan, ActionData
from teddy_executor.core.services.plan_validator import (
    PlanValidator,
    PlanValidationError,
)


def test_validate_edit_action_with_nonexistent_find_block(fs):
    """
    Given a plan with an EDIT action,
    And the target file exists,
    But the FIND block content does not exist in the file,
    When the plan is validated,
    Then a PlanValidationError should be raised.
    """
    # Arrange
    file_path = Path("/app/test.txt")
    fs.create_file(file_path, contents="Hello world")

    plan = Plan(
        actions=[
            ActionData(
                type="edit",
                params={
                    "path": str(file_path),
                    "find": "Goodbye world",
                    "replace": "Hello pytest",
                },
                description="Test edit action validation",
            )
        ]
    )

    validator = PlanValidator()

    # Act & Assert
    with pytest.raises(
        PlanValidationError, match="The `FIND` block could not be located in the file"
    ):
        validator.validate(plan)


def test_validate_edit_action_with_nonexistent_file(fs):
    """
    Given a plan with an EDIT action targeting a non-existent file,
    When the plan is validated,
    Then a PlanValidationError should be raised.
    """
    # Arrange
    file_path = Path("/app/nonexistent.txt")

    plan = Plan(
        actions=[
            ActionData(
                type="edit",
                params={
                    "path": str(file_path),
                    "find": "anything",
                    "replace": "doesn't matter",
                },
                description="Test edit on non-existent file",
            )
        ]
    )

    validator = PlanValidator()

    # Act & Assert
    with pytest.raises(PlanValidationError, match="File to edit does not exist"):
        validator.validate(plan)


def test_validate_edit_action_with_valid_find_block(fs):
    """
    Given a plan with an EDIT action,
    And the FIND block content exists in the file,
    When the plan is validated,
    Then no exception should be raised.
    """
    # Arrange
    file_path = Path("/app/test.txt")
    fs.create_file(file_path, contents="Hello world")

    plan = Plan(
        actions=[
            ActionData(
                type="edit",
                params={
                    "path": str(file_path),
                    "find": "Hello world",
                    "replace": "Hello pytest",
                },
                description="Test edit action validation",
            )
        ]
    )

    validator = PlanValidator()

    # Act & Assert
    try:
        validator.validate(plan)
    except PlanValidationError:
        pytest.fail("PlanValidationError was raised unexpectedly.")
