from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp


def test_reviewer_app_has_consolidated_edit_binding():
    """Verify that 'e' is bound to edit_details and 'p' is removed."""
    # Check bindings (can be tuples or Binding objects)
    binding_keys = [b.key if hasattr(b, "key") else b[0] for b in ReviewerApp.BINDINGS]
    binding_actions = [
        b.action if hasattr(b, "action") else b[1] for b in ReviewerApp.BINDINGS
    ]
    binding_descriptions = [
        b.description if hasattr(b, "description") else b[2]
        for b in ReviewerApp.BINDINGS
    ]

    assert "e" in binding_keys
    assert "edit_details" in binding_actions
    assert "Edit/Preview" in binding_descriptions

    # Check "Execute Step" polish
    assert "x" in binding_keys
    assert "execute_step" in binding_actions
    assert "Execute Step" in binding_descriptions

    # 'p' should be removed
    assert "p" not in binding_keys
    assert "preview" not in binding_actions


def test_reviewer_app_p_action_removed():
    """Ensure action_preview method is removed/renamed."""
    assert hasattr(ReviewerApp, "action_edit_details")
    assert not hasattr(ReviewerApp, "action_preview")
