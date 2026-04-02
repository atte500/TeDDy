import asyncio
import pytest
from unittest.mock import MagicMock, patch
from contextlib import contextmanager

from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser
from teddy_executor.core.ports.outbound import ISystemEnvironment
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager


@contextmanager
def no_op_suspend_cm():
    """A no-op sync context manager to mock app.suspend()."""
    yield


@pytest.mark.anyio
async def test_view_plan_works_with_no_path_but_in_memory_content(env):
    """
    Scenario: Pressing 'v' should work even if the plan has no plan_path,
    as long as the content is known. This test patches app.suspend(), which
    is not supported in Textual's headless test runner.
    """
    # 1. Arrange: Create plan content and a temp file path
    builder = MarkdownPlanBuilder("Robust View Test")
    plan_content = builder.add_execute("ls", description="Test").build()
    temp_file_path = env.workspace / "temp_plan.md"

    # 2. Parse without a path (simulating --plan-content)
    parser = MarkdownPlanParser()
    plan = parser.parse(plan_content)
    assert plan.plan_path is None
    assert plan.raw_content == plan_content

    # 3. Setup App with mocks
    mock_env = env.get_service(ISystemEnvironment)
    mock_fs = env.get_service(IFileSystemManager)
    mock_tooling = MagicMock()

    mock_tooling.find_editor.return_value = ["mock-editor"]
    mock_tooling.get_diff_viewer_command.return_value = None
    # Make the mocked env return a real path for the temp file
    mock_env.create_temp_file.return_value = str(temp_file_path)

    app = ReviewerApp(
        plan=plan,
        system_env=mock_env,
        file_system=mock_fs,
        console_tooling=mock_tooling,
        action_dispatcher=MagicMock(),
    )

    # 4. Act: Trigger 'view_plan', patching the suspend method
    # suspend() returns a context manager, so the mock must return one
    with patch.object(app, "suspend", return_value=no_op_suspend_cm()):
        async with app.run_test() as pilot:
            await pilot.pause()
            # Trigger via keypress
            await pilot.press("v")
            # Give the thread-based worker more time to start and reach the mock
            await asyncio.sleep(0.5)
            await app.workers.wait_for_complete()

    # 5. Assert: Editor was launched and temp file was handled correctly
    mock_env.create_temp_file.assert_called_once_with(suffix=".md")

    # The application code writes to the path provided by the mock
    assert temp_file_path.read_text(encoding="utf-8") == plan_content, (
        "The temp file should contain the plan content"
    )

    # The application code calls run_command and then delete_file
    mock_env.run_command.assert_called_once_with(["mock-editor", str(temp_file_path)])
    mock_env.delete_file.assert_called_once_with(str(temp_file_path))
