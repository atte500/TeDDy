from unittest.mock import MagicMock
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser
from teddy_executor.core.ports.outbound import ISystemEnvironment


def test_tui_view_plan_binding_exists(env):
    """
    As a user, I want to press 'v' in the TUI to view the full plan in my editor.
    """
    # Arrange
    builder = MarkdownPlanBuilder("Test Plan")
    plan_content = builder.add_execute("ls", description="Test").build()

    # Act
    # We verify the binding exists in the App.
    parser = MarkdownPlanParser()
    plan = parser.parse(plan_content, plan_path="my_plan.md")

    system_env = env.get_service(ISystemEnvironment)
    app = ReviewerApp(
        plan=plan,
        system_env=system_env,
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
    )

    # Assert
    # Bindings are defined as list of tuples or Binding objects
    bindings = {
        (b.key if hasattr(b, "key") else b[0]): (
            b.action if hasattr(b, "action") else b[1]
        )
        for b in app.BINDINGS
    }
    assert "v" in bindings, "ReviewerApp should have a 'v' binding"
    assert bindings["v"] == "view_plan", (
        "The 'v' binding should trigger 'view_plan' action"
    )
