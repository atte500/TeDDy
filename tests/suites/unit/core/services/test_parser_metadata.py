import os

import pytest

from teddy_executor.core.ports.inbound.plan_parser import IPlanParser


@pytest.fixture
def parser(container) -> IPlanParser:
    """Resolves the MarkdownPlanParser from the container."""
    return container.resolve(IPlanParser)


def test_parse_execute_action_with_allow_failure(parser: IPlanParser):
    """
    Given an EXECUTE action with Allow Failure metadata,
    When the plan is parsed,
    Then these parameters are correctly extracted.
    """
    # Arrange
    plan_content = """
# Execute with Allow Failure
- Status: Green 🟢
- Agent: Developer

## Rationale
````text
Rationale.
````

## Action Plan

### `EXECUTE`
- Description: Run.
- Allow Failure: true
````shell
pytest
````
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    action = result_plan.actions[0]
    assert action.params.get("allow_failure") is True
    assert action.params["command"] == "pytest"


def test_parse_execute_action_with_background(parser: IPlanParser):
    """
    Given an EXECUTE action with Background metadata set to true,
    When the plan is parsed,
    Then the background parameter is correctly extracted as a boolean.
    """
    # Arrange
    plan_content = """
# Execute in Background
- Status: Green 🟢
- Agent: Developer

## Rationale
````text
Rationale.
````

## Action Plan

### `EXECUTE`
- Description: Start server.
- Background: true
````shell
python -m http.server
````
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    action = result_plan.actions[0]
    assert action.params.get("background") is True
    assert action.params["command"] == "python -m http.server"


def test_parse_execute_action_with_background_false(parser: IPlanParser):
    """
    Given an EXECUTE action with Background metadata set to false,
    When the plan is parsed,
    Then the background parameter is correctly extracted as a boolean.
    """
    # Arrange
    plan_content = """
# Execute normally
- Status: Green 🟢
- Agent: Developer

## Rationale
````text
Rationale.
````

## Action Plan

### `EXECUTE`
- Description: Sync.
- Background: false
````shell
ls
````
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    action = result_plan.actions[0]
    assert action.params.get("background") is False


def test_parse_execute_action_with_timeout(parser: IPlanParser):
    """
    Given an EXECUTE action with Timeout metadata,
    When the plan is parsed,
    Then the timeout parameter is correctly extracted as an integer.
    """
    # Arrange
    expected_timeout = 120
    plan_content = f"""
# Execute with Timeout
- Status: Green 🟢
- Agent: Developer

## Rationale
````text
Rationale.
````

## Action Plan

### `EXECUTE`
- Description: Slow command.
- Timeout: {expected_timeout}
````shell
sleep 10
````
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    action = result_plan.actions[0]
    assert action.params.get("timeout") == expected_timeout


def test_parse_execute_action_with_invalid_timeout(parser: IPlanParser):
    """
    Given an EXECUTE action with non-integer Timeout metadata,
    When the plan is parsed,
    Then the timeout parameter is left as a string (to be caught by validation).
    """
    # Arrange
    plan_content = """
# Execute with Invalid Timeout
- Status: Green 🟢
- Agent: Developer

## Rationale
````text
Rationale.
````

## Action Plan

### `EXECUTE`
- Description: Invalid timeout.
- Timeout: abc
````shell
ls
````
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    action = result_plan.actions[0]
    assert action.params.get("timeout") == "abc"


def test_parse_execute_action_with_cd_directive(parser: IPlanParser):
    """
    Given an EXECUTE action with a `cd` directive in the shell block,
    When the plan is parsed,
    Then the `cd` line remains in the command as it is no longer extracted.
    """
    # Arrange
    plan_content = """
# Execute a command in a specific directory
- **Goal:** Run a test in a subdirectory.

## Rationale
````text
Rationale.
````

## Action Plan

### `EXECUTE`
- **Description:** Run the test suite in `src/`.
- **Expected Outcome:** All tests will pass.
````shell
cd src/my_dir
poetry run pytest
````
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    assert len(result_plan.actions) == 1
    action = result_plan.actions[0]

    assert action.type == "EXECUTE"
    assert action.params["command"] == "cd src/my_dir\npoetry run pytest"


def test_parse_execute_action_with_export_directive(parser: IPlanParser):
    """
    Given an EXECUTE action with `export` directives in the shell block,
    When the plan is parsed,
    Then the `export` lines remain in the command as they are no longer extracted.
    """
    # Arrange
    plan_content = r"""
# Execute a command with environment variables
- **Goal:** Run a command with custom env vars.

## Rationale
````text
Rationale.
````

## Action Plan

### `EXECUTE`
- **Description:** Run a command with env vars.
- **Expected Outcome:** Success.
````shell
export FOO=bar
export BAZ="qux"
export OTHER='single_quotes'
my_command --do-something
````
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    assert len(result_plan.actions) == 1
    action = result_plan.actions[0]

    assert action.type == "EXECUTE"
    expected_cmd = "export FOO=bar\nexport BAZ=\"qux\"\nexport OTHER='single_quotes'\nmy_command --do-something"
    assert action.params["command"] == expected_cmd


def test_parse_execute_action_with_mixed_directives(parser: IPlanParser):
    """
    Given an EXECUTE action with both `cd` and `export` directives,
    When the plan is parsed,
    Then they remain in the command.
    """
    # Arrange
    plan_content = r"""
# Execute a command with mixed directives
- **Goal:** Run a test with context.

## Rationale
````text
Rationale.
````

## Action Plan

### `EXECUTE`
- **Description:** Run pytest in tests dir with CI flag.
- **Expected Outcome:** Success.
````shell
cd tests
export CI=true

pytest -k "my_test"
````
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    assert len(result_plan.actions) == 1
    action = result_plan.actions[0]

    assert action.type == "EXECUTE"
    assert action.params["command"] == 'cd tests\nexport CI=true\n\npytest -k "my_test"'


def test_parse_read_action_with_absolute_path(parser):
    """
    Verify that the parser preserves a true absolute path on the current OS,
    and does not mistakenly treat it as project-root-relative.
    """
    # Arrange: Use an appropriate absolute path for the current OS
    if os.name == "nt":
        absolute_path = "C:\\Users\\test.txt"
    else:
        absolute_path = "/tmp/test.txt"

    plan_content = f"""
# Test Plan
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
````text
Rationale.
````

## Action Plan
### `READ`
- **Resource:** [{absolute_path}]({absolute_path})
- **Description:** Read a file with an absolute path.
"""
    # Act
    plan = parser.parse(plan_content)

    # Assert
    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.type == "READ"

    # The parser normalizes all paths to POSIX style (/) at the boundary.
    expected_path = absolute_path.replace("\\", "/")
    assert action.params["resource"] == expected_path
