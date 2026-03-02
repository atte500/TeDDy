from pathlib import Path

from teddy_executor.core.domain.models.plan import Plan, ActionData
from teddy_executor.core.services.plan_validator import (
    PlanValidator,
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
    file_path = Path("app/test.txt")
    fs.create_file(file_path, contents="Hello world")

    plan = Plan(
        title="Test Plan",
        actions=[
            ActionData(
                type="edit",
                params={
                    "path": str(file_path),
                    "edits": [
                        {"find": "Goodbye world", "replace": "Hello pytest"},
                    ],
                },
                description="Test edit action validation",
            )
        ],
    )

    validator = PlanValidator()

    # Act
    errors = validator.validate(plan)

    # Assert
    assert len(errors) == 1
    assert "The `FIND` block could not be located in the file" in errors[0].message


def test_validate_edit_action_with_nonexistent_file(fs):
    """
    Given a plan with an EDIT action targeting a non-existent file,
    When the plan is validated,
    Then a PlanValidationError should be raised.
    """
    # Arrange
    file_path = Path("app/nonexistent.txt")

    plan = Plan(
        title="Test Plan",
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
        ],
    )

    validator = PlanValidator()

    # Act
    errors = validator.validate(plan)

    # Assert
    assert len(errors) == 1
    assert "File to edit does not exist" in errors[0].message


def test_validate_edit_action_with_valid_find_block(fs):
    """
    Given a plan with an EDIT action,
    And the FIND block content exists in the file,
    When the plan is validated,
    Then no exception should be raised.
    """
    # Arrange
    file_path = Path("app/test.txt")
    fs.create_file(file_path, contents="Hello world")

    plan = Plan(
        title="Test Plan",
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
        ],
    )

    validator = PlanValidator()

    # Act
    errors = validator.validate(plan)

    # Assert
    assert len(errors) == 0, f"Expected no errors, but got: {errors}"


def test_validate_create_fails_if_file_exists(fs):
    """
    Given a CREATE action for a file that exists,
    When validated,
    Then it should return an error.
    """
    fs.create_file("existing.txt", contents="old content")

    plan = Plan(
        title="Test",
        actions=[
            ActionData(type="CREATE", params={"path": "existing.txt", "content": "foo"})
        ],
    )

    validator = PlanValidator()
    errors = validator.validate(plan)

    assert len(errors) == 1
    assert "File already exists" in errors[0].message
    assert errors[0].file_path == "existing.txt"


def test_validate_edit_fails_if_find_block_not_unique(fs):
    """
    Given an EDIT action where the FIND block appears multiple times in the file,
    When validated,
    Then it should return an error.
    """
    content = "def foo():\n    pass\n\ndef foo():\n    pass"
    fs.create_file("source.py", contents=content)

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

    validator = PlanValidator()
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

    validator = PlanValidator()
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

    validator = PlanValidator()
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

    validator = PlanValidator()
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

    validator = PlanValidator()
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

    validator = PlanValidator()
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

    validator = PlanValidator()
    errors = validator.validate(plan)

    assert len(errors) == 0, f"Expected no errors, but got: {errors}"


def test_validate_execute_fails_with_unsafe_cwd_traversal(fs):
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
    validator = PlanValidator()
    errors = validator.validate(plan)

    assert len(errors) == 1
    assert "is outside the project directory" in errors[0].message
    assert errors[0].file_path is None  # Not file-specific error


def test_validate_execute_fails_with_absolute_cwd(fs):
    """
    Given an EXECUTE action where `cwd` is an absolute path,
    When validated,
    Then it should return an error.
    """
    plan = Plan(
        title="Test",
        actions=[
            ActionData(
                type="EXECUTE",
                params={"command": "echo 'test'", "cwd": "/etc/passwd"},
            )
        ],
    )
    validator = PlanValidator()
    errors = validator.validate(plan)

    assert len(errors) == 1
    assert "is an absolute path and is not allowed" in errors[0].message


def test_validate_edit_fails_if_find_and_replace_identical(fs):
    """
    Given an EDIT action where FIND and REPLACE are identical,
    When validated,
    Then it should return an error.
    """
    fs.create_file("source.py", contents="same content")

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

    validator = PlanValidator()
    errors = validator.validate(plan)

    assert len(errors) == 1
    assert "FIND and REPLACE blocks are identical" in errors[0].message


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

    validator = PlanValidator()
    errors = validator.validate(plan)

    assert len(errors) == 1
    assert "Unknown action type: UNKNOWN_ACTION" in errors[0].message
