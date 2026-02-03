import pytest

from teddy_executor.core.domain.models import Plan
from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError
from teddy_executor.core.services.yaml_plan_parser import YamlPlanParser


def test_parse_success_scenario():
    """
    Given a valid plan string,
    When the plan is parsed,
    Then a valid Plan domain object is returned.
    """
    # Arrange
    plan_content = """
    actions:
      - type: create_file
        params:
            path: "hello.txt"
            content: "Hello, World!"
      - type: execute
        params:
            command: "echo 'done'"
    """
    plan_parser = YamlPlanParser()

    # Act
    result_plan = plan_parser.parse(plan_content=plan_content)

    # Assert
    assert isinstance(result_plan, Plan)
    assert len(result_plan.actions) == 2

    assert result_plan.actions[0].type == "create_file"
    assert result_plan.actions[0].params == {
        "path": "hello.txt",
        "content": "Hello, World!",
    }

    assert result_plan.actions[1].type == "execute"
    assert result_plan.actions[1].params == {"command": "echo 'done'"}


def test_parse_raises_invalid_plan_error_for_malformed_yaml():
    """
    Given a plan string with syntactically incorrect YAML,
    When the plan is parsed,
    Then an InvalidPlanError should be raised.
    """
    # Arrange
    malformed_content = "actions:\n\t- type: create_file"
    plan_parser = YamlPlanParser()

    # Act & Assert
    with pytest.raises(InvalidPlanError, match="Plan contains invalid YAML"):
        plan_parser.parse(plan_content=malformed_content)


def test_parse_raises_invalid_plan_error_for_empty_content():
    """
    Given an empty string,
    When the plan is parsed,
    Then an InvalidPlanError should be raised.
    """
    # Arrange
    plan_parser = YamlPlanParser()

    # Act & Assert
    with pytest.raises(InvalidPlanError, match="Plan content cannot be empty"):
        plan_parser.parse(plan_content="  ")
