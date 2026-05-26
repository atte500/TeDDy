from teddy_executor.core.domain.models.plan import ActionType, ActionData


def test_action_type_includes_message():
    assert "MESSAGE" in ActionType.__members__
    assert ActionType.MESSAGE == "MESSAGE"


def test_message_action_is_terminal():
    # As per the spec, MESSAGE is a terminal action/section.
    action = ActionData(type=ActionType.MESSAGE, params={})
    assert action.is_terminal is True
