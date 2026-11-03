import pytest
from unittest.mock import MagicMock, patch
from teddy_executor.core.domain.models.plan import Plan, ActionData
from teddy_executor.adapters.inbound.textual_plan_reviewer_previews import (
    view_plan_handler,
)


@pytest.mark.anyio
async def test_view_plan_handler_reads_full_plan_and_opens_persistent_path():
    # Setup
    mock_app = MagicMock()
    mock_app._file_system = MagicMock()
    mock_app._file_system.read_raw_file.return_value = "Mocked Plan Content"
    mock_app.config_service = None

    plan_path = "some/real/path/plan.md"
    dummy_action = MagicMock(spec=ActionData)
    mock_app.plan = Plan(
        title="Test Plan",
        rationale="Rationale",
        actions=[dummy_action],
        plan_path=plan_path,
    )

    with patch(
        "teddy_executor.adapters.inbound.textual_plan_reviewer_previews.launch_editor"
    ) as mock_launch:
        mock_launch.return_value = None

        # Execute
        await view_plan_handler(mock_app)

        # Assert: read untruncated, then opened read-only in place (no truncation)
        mock_app._file_system.read_raw_file.assert_called_once_with(plan_path)
        mock_launch.assert_called_once()
        _, kwargs = mock_launch.call_args
        assert kwargs.get("persistent_path") == plan_path
        assert kwargs.get("skip_confirm") is True


@pytest.mark.anyio
async def test_view_plan_handler_truncates_a_long_plan_with_hint_less_notice(tmp_path):
    mock_app = MagicMock()
    mock_app._file_system = MagicMock()
    long_plan = "\n".join(f"line {i}" for i in range(1, 601))
    mock_app._file_system.read_raw_file.return_value = long_plan

    plan_path = "some/real/path/plan.md"
    dummy_action = MagicMock(spec=ActionData)
    mock_app.plan = Plan(
        title="Test Plan",
        rationale="Rationale",
        actions=[dummy_action],
        plan_path=plan_path,
    )

    config_service = MagicMock()
    config_service.get_setting.return_value = 200
    mock_app.config_service = config_service

    view_temp = str(tmp_path / "plan_view.md")
    mock_app._system_env = MagicMock()
    mock_app._system_env.create_temp_file.return_value = view_temp
    mock_app._log_preview_files = []

    with patch(
        "teddy_executor.adapters.inbound.textual_plan_reviewer_previews.launch_editor"
    ) as mock_launch:
        mock_launch.return_value = None
        await view_plan_handler(mock_app)

    mock_app._file_system.read_raw_file.assert_called_once_with(plan_path)
    rendered = mock_launch.call_args.args[1]
    lines = rendered.splitlines()
    assert lines[:200] == [f"line {i}" for i in range(1, 201)]
    assert lines[200] == "[Showing first 200 of 600 lines.]"
    assert "Use the 'Lines' parameter" not in rendered
    _, kwargs = mock_launch.call_args
    assert kwargs.get("persistent_path") == view_temp
    assert kwargs.get("skip_confirm") is True

    from pathlib import Path

    assert Path(view_temp).read_text(encoding="utf-8") == rendered
