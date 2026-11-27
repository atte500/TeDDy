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


def test_resolve_action_parameters_lists_move_source_then_destination():
    # Arrange: A MOVE carries the plan's own vocabulary, not a single path
    action = ActionData(
        type=ActionType.MOVE,
        params={"source": "a/old.py", "destination": "a/new.py"},
    )

    # Act
    resolved = resolve_action_parameters(action)

    # Assert
    assert list(resolved) == ["source", "destination"]
    assert resolved["source"] == "a/old.py"
    assert resolved["destination"] == "a/new.py"


def test_resolve_action_parameters_renders_absent_recursive_as_false():
    # Arrange: Destructive intent stated by omission must read as False
    action = ActionData(type=ActionType.DELETE, params={"path": "a/legacy"})

    # Act
    resolved = resolve_action_parameters(action)

    # Assert
    assert list(resolved) == ["path", "recursive"]
    assert resolved["recursive"] is False
