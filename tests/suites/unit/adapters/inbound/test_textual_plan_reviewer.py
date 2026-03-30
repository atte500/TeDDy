import pytest
from unittest.mock import Mock
from teddy_executor.core.domain.models.plan import Plan, ActionData
from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer
from teddy_executor.adapters.inbound.textual_plan_reviewer import (
    TextualPlanReviewer,
    ReviewerApp,
)
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager


def test_textual_plan_reviewer_implements_protocol(container):
    """
    Verify that TextualPlanReviewer implements the IPlanReviewer protocol.
    """
    # Arrange
    reviewer = TextualPlanReviewer(
        system_env=container.resolve(ISystemEnvironment),
        file_system=container.resolve(IFileSystemManager),
    )

    # Assert
    assert isinstance(reviewer, IPlanReviewer)


def test_review_returns_plan_unchanged_in_non_interactive_mock(container, monkeypatch):
    """
    Verify the review entry point exists and returns a plan.
    (Note: This is a shallow test before we implement the actual App logic)
    """
    # Arrange
    reviewer = TextualPlanReviewer(
        system_env=container.resolve(ISystemEnvironment),
        file_system=container.resolve(IFileSystemManager),
    )
    plan = Plan(title="Test", rationale="Test", actions=[Mock(selected=True)])

    # Act
    # We'll mock the internal app.run() to avoid launching a TUI during unit tests
    monkeypatch.setattr(reviewer, "_run_app", lambda p: p)
    result = reviewer.review(plan)

    # Assert
    assert result == plan


@pytest.mark.anyio
@pytest.mark.parametrize(
    "action_type, param_key",
    [
        ("EXECUTE", "command"),
        ("RESEARCH", "queries"),
    ],
)
async def test_reviewer_app_preview_text_actions(
    env, monkeypatch, action_type, param_key
):
    """Verify that p key (preview) triggers editing for simple text-based actions."""
    # 1. Setup plan with target action
    action = ActionData(
        type=action_type,
        params={param_key: "original content", "description": "test"},
        selected=True,
    )
    plan = Plan(
        title="Test Plan",
        rationale="Test",
        actions=[action],
        metadata={"agent": "Pathfinder"},
    )

    # 2. Mock environment for editor
    sys_env = env.get_service(ISystemEnvironment)
    sys_env.get_env.side_effect = lambda k: "mock-editor" if k == "VISUAL" else None
    monkeypatch.setenv("TEDDY_TEST_MOCK_EDITOR_OUTPUT", "modified content")

    # 3. Run app and trigger preview
    app = ReviewerApp(
        plan=plan, system_env=sys_env, file_system=env.get_mock_filesystem()
    )
    async with app.run_test() as pilot:
        await pilot.press("down")
        await pilot.press("p")
        await pilot.wait_for_scheduled_animations()
        await pilot.press("y")
        await pilot.wait_for_scheduled_animations()

    # 4. Assert modification
    assert action.params[param_key] == "modified content"
    assert action.modified is True


@pytest.mark.anyio
@pytest.mark.parametrize("action_type", ["READ", "PRUNE"])
async def test_reviewer_app_preview_readonly_actions(env, action_type):
    """Verify that p key (preview) triggers viewing for READ/PRUNE actions."""
    # 1. Setup plan with target action
    action = ActionData(
        type=action_type,
        params={"resource": "README.md", "description": "test"},
        selected=True,
    )
    plan = Plan(title="Test", rationale="Test", actions=[action], is_session=True)

    # 2. Mock filesystem
    fs = env.get_mock_filesystem()
    fs.read_file.return_value = "file content"

    # 3. Run app and trigger preview
    sys_env = env.get_service(ISystemEnvironment)
    app = ReviewerApp(plan=plan, system_env=sys_env, file_system=fs)
    async with app.run_test() as pilot:
        await pilot.press("down")
        await pilot.press("p")
        await pilot.wait_for_scheduled_animations()

    # 4. Assert NO modification occurred
    assert action.modified is False
    fs.read_file.assert_called_with("README.md")
