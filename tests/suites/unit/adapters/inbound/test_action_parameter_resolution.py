from teddy_executor.core.domain.models.plan import ActionData, ActionType
from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
    resolve_action_parameters,
)


def test_resolve_action_parameters_includes_defaults():
    # Arrange: Action with missing optional parameters
    action = ActionData(type=ActionType.CREATE, params={"path": "test.txt"})

    # Act
    resolved = resolve_action_parameters(action)

    # Assert
    assert resolved["path"] == "test.txt"
    assert resolved["overwrite"] is False  # Default


def test_resolve_action_parameters_respects_provided_values():
    # Arrange: Action with explicit non-default values
    expected_timeout = 100
    action = ActionData(
        type=ActionType.EXECUTE, params={"command": "ls", "timeout": expected_timeout}
    )

    # Act
    resolved = resolve_action_parameters(action)

    # Assert
    assert resolved["command"] == "ls"
    assert resolved["timeout"] == expected_timeout
    assert resolved["allow_failure"] is False  # Other default for EXECUTE
