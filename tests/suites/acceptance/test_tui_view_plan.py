from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp


def test_tui_view_plan_binding_exists():
    """
    As a user, I want to press 'v' in the TUI to view the full plan in my editor.
    """
    # Arrange & Act
    # We verify the binding exists directly on the App class.

    # Assert
    # Bindings are defined as list of tuples or Binding objects
    bindings = {
        (b.key if hasattr(b, "key") else b[0]): (
            b.action if hasattr(b, "action") else b[1]
        )
        for b in ReviewerApp.BINDINGS
    }
    assert "v" in bindings, "ReviewerApp should have a 'v' binding"
    assert bindings["v"] == "view_plan", (
        "The 'v' binding should trigger 'view_plan' action"
    )
