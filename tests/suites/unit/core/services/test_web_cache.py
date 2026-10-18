"""Regression test for Bug #10: Web Cache Ignored Each Turn.

Verifies that PlanningService.generate_plan() passes cache_dir to get_context()
so that the web content cache is used during planning.
"""

from unittest.mock import MagicMock
from pathlib import Path

from teddy_executor.core.domain.models.planning_ports import PlanningPorts
from teddy_executor.core.services.planning_service import PlanningService


def test_planning_service_passes_cache_dir():
    """PlanningService.generate_plan() must pass cache_dir to get_context()."""
    # Arrange: Create mock ports with a tracked context_service
    mock_context = MagicMock()
    mock_context.get_context.return_value = MagicMock(
        header="",
        content="",
        items=[],
        agent_name="test",
        total_window=0,
        system_prompt_tokens=0,
        content_tokens=0,
    )

    mock_llm = MagicMock()
    mock_llm.validate_config.return_value = []

    mock_fs = MagicMock()
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = ""
    mock_fs.list_directory.return_value = ["test_agent.xml"]
    mock_fs.read_files_in_vault.return_value = {}
    mock_fs.is_dir.return_value = False

    mock_config = MagicMock()
    mock_config.get_setting.return_value = "test-model"

    mock_prompts = MagicMock()
    mock_prompts.resolve_agent_metadata.return_value = (
        "test_agent",
        {"model": "test-model", "is_replan": False},
        "/tmp/meta.yaml",
    )
    mock_prompts.fetch_system_prompt.return_value = "system prompt"
    mock_prompts.resolve_message.return_value = "test message"
    mock_prompts.get_available_agents.return_value = ["test_agent"]
    mock_prompts.log_telemetry.return_value = 0.0
    mock_prompts.update_meta = MagicMock()

    mock_ui = MagicMock()
    mock_session = MagicMock()
    mock_session.resolve_context_paths.return_value = {"Session": [], "Turn": []}

    ports = PlanningPorts(
        context=mock_context,
        llm=mock_llm,
        fs=mock_fs,
        config=mock_config,
        prompts=mock_prompts,
        ui=mock_ui,
        session_manager=mock_session,
    )

    service = PlanningService(ports)

    # We need to avoid actual LLM call; patch _perform_generation_with_retry
    service._perform_generation_with_retry = MagicMock(
        return_value=(MagicMock(), "plan content", 0.0)
    )
    service._display_telemetry = MagicMock()
    service._safe_float = MagicMock(return_value=0.0)

    turn_dir = "/tmp/.teddy/sessions/test-session/01"

    # Act: Call generate_plan
    service.generate_plan(user_message="test", turn_dir=turn_dir)

    # Assert: get_context was called with cache_dir = parent of turn_dir
    expected_cache_dir = str(Path(turn_dir).parent)  # /tmp/.teddy/sessions/test-session
    call_kwargs = mock_context.get_context.call_args.kwargs
    assert "cache_dir" in call_kwargs, (
        f"cache_dir not in get_context kwargs: {call_kwargs}"
    )
    assert call_kwargs["cache_dir"] == expected_cache_dir, (
        f"Expected cache_dir={expected_cache_dir}, got {call_kwargs['cache_dir']}"
    )
    print(f"PASS: PlanningService passes cache_dir='{call_kwargs['cache_dir']}'")
