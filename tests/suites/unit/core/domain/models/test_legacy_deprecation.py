from teddy_executor.core.domain.models.plan import ActionType


def test_legacy_actions_are_removed_from_enum():
    """Verify that legacy action types are no longer part of the ActionType contract."""
    legacy_actions = ["PROMPT", "INVOKE", "RETURN", "PRUNE"]

    for action in legacy_actions:
        assert action not in ActionType.__members__, (
            f"ActionType.{action} should be removed."
        )
