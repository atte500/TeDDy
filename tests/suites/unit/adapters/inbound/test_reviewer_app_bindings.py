import pytest
from unittest.mock import MagicMock
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.core.domain.models.plan import Plan, ActionData


@pytest.fixture
def reviewer_app():
    """Fixture to provide a ReviewerApp instance with a valid plan."""
    action = ActionData(type="EXECUTE", params={"command": "ls"}, description="test")
    plan = Plan(
        title="Test Plan", rationale="Test Rationale", actions=[action], metadata={}
    )
    return ReviewerApp(
        plan=plan,
        system_env=MagicMock(),
        console_tooling=MagicMock(),
        file_system=MagicMock(),
        action_dispatcher=MagicMock(),
    )


def test_reviewer_app_has_consolidated_edit_binding(reviewer_app):
    """Verify that 'e' is bound to edit_details and 'p' is removed."""
    # Check bindings (currently defined as tuples in ReviewerApp)
    binding_keys = [b[0] for b in reviewer_app.BINDINGS]
    binding_actions = [b[1] for b in reviewer_app.BINDINGS]
    binding_descriptions = [b[2] for b in reviewer_app.BINDINGS]

    assert "e" in binding_keys
    assert "edit_details" in binding_actions
    assert "Edit/Details" in binding_descriptions

    # Check "Execute Step" polish
    assert "x" in binding_keys
    assert "execute_step" in binding_actions
    assert "Execute Step" in binding_descriptions

    # 'p' should be removed
    assert "p" not in binding_keys
    assert "preview" not in binding_actions


def test_reviewer_app_p_action_removed(reviewer_app):
    """Ensure action_preview method is removed/renamed."""
    assert hasattr(reviewer_app, "action_edit_details")
    assert not hasattr(reviewer_app, "action_preview")
