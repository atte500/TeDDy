import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from contextlib import asynccontextmanager
from teddy_executor.adapters.inbound.textual_plan_reviewer import (
    ReviewerApp,
    ConfirmScreen,
)
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


@asynccontextmanager
async def mock_suspend():
    yield


@pytest.fixture
def plan():
    builder = MarkdownPlanBuilder("Confirm Test")
    builder.add_edit("file.txt", "find", "replace")
    builder.add_create("new.txt", "content")
    builder.add_execute("ls")
    p = MarkdownPlanParser().parse(builder.build())
    p.metadata["user_request"] = "original message"
    return p


async def wait_for_confirm_screen(app, timeout=2.0):
    """Wait for the ConfirmScreen to be pushed and active."""
    start = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start < timeout:
        if isinstance(app.screen, ConfirmScreen):
            return
        await asyncio.sleep(0.05)
    raise TimeoutError(f"ConfirmScreen did not appear. Current screen: {app.screen}")


@pytest.mark.anyio
async def test_add_message_cancellation(plan, tmp_path):
    """Scenario: Changes to the message MUST NOT be applied if cancelled."""
    mock_env = MagicMock()
    # Ensure unique paths to avoid Bad file descriptor
    mock_env.create_temp_file.side_effect = lambda suffix=".txt": str(
        tmp_path / f"temp_{suffix[1:]}"
    )
    mock_tooling = MagicMock()
    mock_tooling.find_editor.return_value = ["mock-editor"]
    app = ReviewerApp(plan, mock_env, mock_tooling)

    with patch.object(app, "suspend", side_effect=mock_suspend):
        with patch(
            "teddy_executor.adapters.inbound.textual_plan_reviewer.launch_editor",
            new_callable=AsyncMock,
        ) as mock_launch:
            mock_launch.return_value = "new message"
            async with app.run_test() as pilot:
                worker = app.action_add_message()
                await wait_for_confirm_screen(app)
                await pilot.press("n")
                await worker.wait()
                assert plan.metadata["user_request"] == "original message"


@pytest.mark.anyio
async def test_add_message_confirmation(plan, tmp_path):
    """Scenario: Changes to the message MUST be applied if confirmed."""
    mock_env = MagicMock()
    mock_env.create_temp_file.side_effect = lambda suffix=".txt": str(
        tmp_path / f"temp_{suffix[1:]}"
    )
    mock_tooling = MagicMock()
    mock_tooling.find_editor.return_value = ["mock-editor"]
    app = ReviewerApp(plan, mock_env, mock_tooling)

    with patch.object(app, "suspend", side_effect=mock_suspend):
        with patch(
            "teddy_executor.adapters.inbound.textual_plan_reviewer.launch_editor",
            new_callable=AsyncMock,
        ) as mock_launch:
            mock_launch.return_value = "new message"
            async with app.run_test() as pilot:
                worker = app.action_add_message()
                await wait_for_confirm_screen(app)
                await pilot.press("y")
                await worker.wait()

                # With deferred processing, we must submit to see the update
                app.action_submit()
                assert plan.metadata["user_request"] == "new message"


@pytest.mark.anyio
async def test_preview_edit_cancellation(plan, tmp_path):
    """Scenario: Previewing/Modifying an EDIT action MUST NOT be applied if cancelled."""
    mock_env = MagicMock()
    mock_env.create_temp_file.side_effect = lambda suffix=".txt": str(
        tmp_path / f"temp_{suffix[1:]}"
    )
    mock_tooling = MagicMock()
    # Force single-file editor path
    mock_tooling.get_diff_viewer_command.return_value = None
    mock_fs = MagicMock()
    mock_fs.read_file.return_value = "find"
    mock_tooling.find_editor.return_value = ["mock-editor"]
    app = ReviewerApp(plan, mock_env, mock_tooling, file_system=mock_fs)
    action = plan.actions[0]

    with patch.object(app, "suspend", side_effect=mock_suspend):
        with patch(
            "teddy_executor.adapters.inbound.textual_plan_reviewer_logic.launch_editor",
            new_callable=AsyncMock,
        ) as mock_launch:
            mock_launch.return_value = "modified content"
            async with app.run_test() as pilot:
                await pilot.pause()
                # Focus the first action (index 0 is header)
                await pilot.press("down")
                # Trigger preview via 'p'
                await pilot.press("p")
                await wait_for_confirm_screen(app)
                await pilot.press("n")
                # Wait for all workers to finish
                await app.workers.wait_for_complete()
                assert action.params.get("content") is None
                assert not action.modified


@pytest.mark.anyio
async def test_preview_edit_confirmation(plan, tmp_path):
    """Scenario: Previewing/Modifying an EDIT action MUST be applied if confirmed."""
    mock_env = MagicMock()
    mock_env.create_temp_file.side_effect = lambda suffix=".txt": str(
        tmp_path / f"temp_{suffix[1:]}"
    )
    mock_tooling = MagicMock()
    # Force single-file editor path
    mock_tooling.get_diff_viewer_command.return_value = None
    mock_fs = MagicMock()
    mock_fs.read_file.return_value = "find"
    mock_tooling.find_editor.return_value = ["mock-editor"]
    app = ReviewerApp(plan, mock_env, mock_tooling, file_system=mock_fs)
    action = plan.actions[0]

    with patch.object(app, "suspend", side_effect=mock_suspend):
        with patch(
            "teddy_executor.adapters.inbound.textual_plan_reviewer_logic.launch_editor",
            new_callable=AsyncMock,
        ) as mock_launch:
            mock_launch.return_value = "modified content"
            async with app.run_test() as pilot:
                await pilot.pause()
                # Focus the first action (index 0 is header)
                await pilot.press("down")
                # Trigger preview via 'p'
                await pilot.press("p")
                await wait_for_confirm_screen(app)
                await pilot.press("y")
                # Wait for all workers to finish
                await app.workers.wait_for_complete()
                assert action.params.get("content") == "modified content"
                assert action.modified
