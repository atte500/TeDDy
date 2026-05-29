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
