import pytest

from teddy_executor.core.domain.models.plan import ActionData, ActionType, Plan


def test_plan_is_communication_turn():
    # Only MESSAGE action
    plan_msg = Plan(
        title="Msg",
        rationale="Rat",
        actions=[ActionData(type=ActionType.MESSAGE, params={"content": "hi"})],
    )
    assert plan_msg.is_communication_turn() is True

    # MESSAGE + other action
    plan_mixed = Plan(
        title="Mixed",
        rationale="Rat",
        actions=[
            ActionData(type=ActionType.MESSAGE, params={"content": "hi"}),
            ActionData(type=ActionType.CREATE, params={"path": "f.txt"}),
        ],
    )
    assert plan_mixed.is_communication_turn() is False

    # Standard action
    plan_create = Plan(
        title="Create",
        rationale="Rat",
        actions=[ActionData(type=ActionType.CREATE, params={"path": "f.txt"})],
    )
    assert plan_create.is_communication_turn() is False


def _plan_with_stamps(stamps: list[int | None]) -> Plan:
    """Builds a plan whose actions carry the given execution stamps."""
    return Plan(
        title="Stamp plan",
        rationale="Rat",
        actions=[
            ActionData(
                type=ActionType.CREATE,
                params={"path": f"file{index}.txt"},
                execution_sequence=stamp,
            )
            for index, stamp in enumerate(stamps)
        ],
    )


def test_action_execution_sequence_defaults_to_none():
    action = ActionData(type=ActionType.CREATE, params={"path": "file.txt"})

    assert action.execution_sequence is None


@pytest.mark.parametrize(
    "stamps, expected",
    [
        ([None, None], 1),
        ([1], 2),
        ([1, None, 3], 4),
        ([2, 2], 3),
    ],
)
def test_plan_next_execution_sequence_is_the_highest_stamp_plus_one(stamps, expected):
    assert _plan_with_stamps(stamps).next_execution_sequence() == expected
