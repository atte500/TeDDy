from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator


def test_validate_execute_action_allows_multiline_commands(container):
    """
    Given an EXECUTE action with multiple commands,
    When validated,
    Then it should return no errors.
    """
    validator = container.resolve(IPlanValidator)
    """
    Given an EXECUTE action with multiple commands,
    When validated,
    Then it should return no errors.
    """
    plan = Plan(
        title="Test",
        rationale="Test",
        actions=[
            ActionData(
                type="EXECUTE",
                params={"command": "echo 'hello'\necho 'world'"},
            )
        ],
    )

    errors = validator.validate(plan)

    assert len(errors) == 0


def test_validate_execute_action_allows_chained_commands(container):
    validator = container.resolve(IPlanValidator)
    """
    Given an EXECUTE action with any chaining operator (&&, ||, ;, |, &),
    When validated,
    Then it should return no errors.
    """
    for op in ["&&", "||", ";", "|", "&"]:
        plan = Plan(
            title="Test",
            rationale="Test",
            actions=[
                ActionData(
                    type="EXECUTE",
                    params={"command": f"echo 'hello' {op} echo 'world'"},
                )
            ],
        )

        errors = validator.validate(plan)

        assert len(errors) == 0, f"Failed for operator {op}"


def test_validate_execute_succeeds_for_single_command_with_line_continuations(
    container,
):
    validator = container.resolve(IPlanValidator)
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
        rationale="Test",
        actions=[ActionData(type="EXECUTE", params={"command": command})],
    )

    errors = validator.validate(plan)

    assert len(errors) == 0, (
        f"Expected no errors for line continuation, but got: {errors}"
    )


def test_validate_execute_succeeds_for_single_command_with_multiline_argument(
    container,
):
    validator = container.resolve(IPlanValidator)
    """
    Given a single command with a multiline string argument,
    When validated,
    Then it should not return an error.
    """
    command = "git commit -m 'Subject\n\nThis is the body.'"
    plan = Plan(
        title="Test",
        rationale="Test",
        actions=[ActionData(type="EXECUTE", params={"command": command})],
    )

    errors = validator.validate(plan)

    assert len(errors) == 0, (
        f"Expected no errors for multiline argument, but got: {errors}"
    )


def test_validate_execute_succeeds_with_ampersands_in_quoted_string(container):
    validator = container.resolve(IPlanValidator)
    """
    Given an EXECUTE action with '&&' inside a quoted string,
    When validated,
    Then it should not return an error.
    """
    command = "echo 'hello && world'"
    plan = Plan(
        title="Test",
        rationale="Test",
        actions=[ActionData(type="EXECUTE", params={"command": command})],
    )

    errors = validator.validate(plan)

    assert len(errors) == 0, (
        f"Expected no errors for quoted ampersands, but got: {errors}"
    )


def test_validate_execute_action_allows_directives(container):
    validator = container.resolve(IPlanValidator)
    """
    Given an EXECUTE action with 'cd' or 'export' in the command block,
    When validated,
    Then it should return no errors.
    """
    for directive in ["cd /tmp", "export FOO=bar"]:
        plan = Plan(
            title="Test",
            rationale="Test",
            actions=[
                ActionData(
                    type="EXECUTE",
                    params={"command": f"{directive}\nls -l"},
                )
            ],
        )

        errors = validator.validate(plan)

        assert len(errors) == 0


def test_validate_execute_fails_with_posix_absolute_cwd(container):
    validator = container.resolve(IPlanValidator)
    """
    Given an EXECUTE action with a POSIX absolute CWD (starting with /),
    When validated,
    Then it should return a validation error.
    """
    plan = Plan(
        title="Test",
        rationale="Test",
        actions=[
            ActionData(
                type="EXECUTE",
                params={"command": "ls", "cwd": "/etc"},
            )
        ],
    )

    errors = validator.validate(plan)

    assert len(errors) == 1
    assert "is an absolute path and is not allowed" in errors[0].message


def test_validate_execute_fails_with_traversal_cwd(container):
    validator = container.resolve(IPlanValidator)
    """
    Given an EXECUTE action with a CWD containing traversal (..),
    When validated,
    Then it should return a validation error.
    """
    plan = Plan(
        title="Test",
        rationale="Test",
        actions=[
            ActionData(
                type="EXECUTE",
                params={"command": "ls", "cwd": "../secret"},
            )
        ],
    )

    errors = validator.validate(plan)

    assert len(errors) == 1
    assert "is outside the project directory" in errors[0].message


def test_validate_execute_fails_with_unsafe_cwd_traversal(container):
    validator = container.resolve(IPlanValidator)
    """
    Given an EXECUTE action where `cwd` attempts to traverse outside the project root,
    When validated,
    Then it should return an error.
    """
    plan = Plan(
        title="Test",
        rationale="Test",
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


def test_validate_execute_fails_with_absolute_cwd(container):
    validator = container.resolve(IPlanValidator)
    """
    Given an EXECUTE action where `cwd` is an absolute path,
    When validated,
    Then it should return an error.
    """
    import os

    absolute_cwd = "/etc/passwd" if os.name != "nt" else "C:\\Windows"

    plan = Plan(
        title="Test",
        rationale="Test",
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
