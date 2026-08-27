import pytest
from unittest.mock import MagicMock
from teddy_executor.core.domain.models.plan import Plan, ActionData, ExecutionStatus
from teddy_executor.core.domain.models.execution_report import ActionLog, ActionStatus
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
    format_node_label,
)
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment


def test_format_node_label_with_execution_state():
    action = ActionData(type="EXECUTE", params={"command": "ls"}, selected=True)
    action.executed = True
    action.state = ExecutionStatus.SUCCESS
    label = format_node_label(action)
    assert "[green][SUCCESS]" in label
    assert "EXECUTE: ls" in label


@pytest.mark.anyio
async def test_reviewer_app_execute_key(env):
    action = ActionData(type="EXECUTE", params={"command": "ls"}, selected=True)
    plan = Plan(title="T", rationale="R", actions=[action])
    mock_dispatcher = MagicMock()
    mock_dispatcher.dispatch_and_execute.return_value = ActionLog(
        status=ActionStatus.SUCCESS, action_type="EXECUTE", params={}
    )
    app = ReviewerApp(
        plan=plan,
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=MagicMock(),
        action_dispatcher=mock_dispatcher,
    )
    async with app.run_test() as pilot:
        await pilot.press("down", "down", "down")
        await pilot.press("x")
        await pilot.wait_for_scheduled_animations()
        await app.workers.wait_for_complete()
        assert action.executed is True
        assert action.state == ExecutionStatus.SUCCESS


@pytest.mark.anyio
async def test_reviewer_app_context_tree_population(env):
    # Arrange
    from teddy_executor.core.domain.models.project_context import (
        ProjectContext,
        ContextItem,
    )
    from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import ActionTree

    item = ContextItem(
        path="src/core.py", token_count=1200, git_status="M", scope="Session"
    )
    context = ProjectContext(
        header="H", content="C", items=[item], agent_name="Architect"
    )
    from teddy_executor.core.domain.models.plan import ActionData

    plan = Plan(
        title="T",
        rationale="R",
        actions=[ActionData(type="READ", params={"path": "test.py"})],
    )

    app = ReviewerApp(
        plan=plan,
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
        project_context=context,
    )

    # Act
    async with app.run_test():
        tree = app.query_one(ActionTree)

        # Assert - Hierarchy matching Prototype/Specs
        # Root is hidden, children of root should be: Context, Rationale, Action Plan
        root_children = tree.root.children
        assert str(root_children[0].label) == "Context"
        assert root_children[0].data == "CONTEXT_ROOT"
        assert root_children[0].is_expanded is False

        # Verify scope labels and items under Context
        context_node = root_children[0]
        context_children = context_node.children

        # Prototype order: System -> Session -> Turn
        # System is always added in prototype even if empty items
        assert "System:" in str(context_children[0].label)
        assert "Session:" in str(context_children[2].label)

        # Verify file item formatting (indented, path, status)
        file_node = context_children[3]
        assert file_node.data == item
        assert "  src/core.py" in str(file_node.label)
        assert "[M]" in str(file_node.label)
        assert "1.2k" in str(file_node.label)


def test_pending_message_file_restored_from_plan_metadata(env, tmp_path):
    """When a plan has 'pending_message_file' in metadata, a new ReviewerApp
    restores it as _pending_message_file and reuses it.

    This is the core unit test for the Logic (TUI) deliverable: persistent
    temp file storage across launches via plan metadata.
    """
    from unittest.mock import MagicMock
    from teddy_executor.core.domain.models.plan import Plan, ActionData
    from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
    from teddy_executor.core.ports.outbound.system_environment import (
        ISystemEnvironment,
    )

    # Arrange: create a plan with a pre-existing pending_message_file metadata
    pending_file = str(tmp_path / "pending_message.md")
    # Write some initial content to the file
    with open(pending_file, "w", encoding="utf-8") as f:
        f.write("Initial content")
    plan = Plan(
        title="Test",
        rationale="Test",
        actions=[ActionData(type="MESSAGE", params={})],
    )
    plan.metadata["pending_message_file"] = pending_file

    system_env = env.container.resolve(ISystemEnvironment)

    console_tooling = MagicMock()
    console_tooling.get_diff_viewer_command.return_value = None
    console_tooling.find_editor.return_value = ["/usr/bin/vim"]

    # Act: create a new ReviewerApp with this plan
    app = ReviewerApp(
        plan=plan,
        system_env=system_env,
        console_tooling=console_tooling,
        action_dispatcher=MagicMock(),
        file_system=MagicMock(),
    )

    # Assert: app._pending_message_file should be restored from plan metadata
    assert hasattr(app, "_pending_message_file"), (
        "ReviewerApp should have _pending_message_file attribute"
    )
    assert app._pending_message_file == pending_file, (
        f"Expected {pending_file}, got {app._pending_message_file}"
    )
