import pytest
from teddy_executor.core.services.planning_service import PlanningService


@pytest.mark.anyio
async def test_planning_service_has_async_generate_plan_seam():
    # Setup: Create service with mocked dependencies
    from unittest.mock import AsyncMock, MagicMock

    mock_context = AsyncMock()
    # Context must have header and content attributes
    mock_context_result = MagicMock()
    mock_context_result.header = "Header"
    mock_context_result.content = "Content"
    mock_context.async_get_context.return_value = mock_context_result

    # LLM Client has both sync and async methods.
    # Use MagicMock and selectively assign AsyncMock to async methods.
    mock_llm = MagicMock()
    # Mocking the response to avoid structural validation errors
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[
        0
    ].message.content = "# Plan\n- **Agent:** pathfinder\n- **Status:** SUCCESS\n\n## Rationale\n~~~~~~\nTest\n~~~~~~\n\n## Action Plan\n### EXECUTE\n- Description: test\n~~~~~~shell\necho 1\n~~~~~~\n"
    mock_response.model = "test-model"

    mock_llm.async_get_completion = AsyncMock(return_value=mock_response)
    mock_llm.get_completion_cost.return_value = 0.01
    mock_llm.get_token_count.return_value = 100

    from teddy_executor.core.domain.models.planning_ports import PlanningPorts
    from unittest.mock import AsyncMock, MagicMock

    mock_pm = MagicMock()
    mock_pm.async_resolve_message = AsyncMock(return_value="test message")
    mock_pm.resolve_agent_metadata.return_value = ("pathfinder", {}, "meta.yaml")
    mock_pm.async_fetch_system_prompt = AsyncMock(return_value="system prompt")
    mock_pm.async_log_telemetry = AsyncMock(return_value=0.01)

    service = PlanningService(
        PlanningPorts(
            context=mock_context,
            llm=mock_llm,
            fs=MagicMock(),
            config=MagicMock(),
            prompts=mock_pm,
            ui=AsyncMock(),
        )
    )

    # Act: Execute the now-implemented method
    plan_path, cost = await service.async_generate_plan(
        user_message="test", turn_dir="test_dir"
    )

    # Assert: Method successfully generates a plan (proves implementation exists)
    EXPECTED_COST = 0.01
    assert plan_path is not None
    assert cost == EXPECTED_COST


@pytest.mark.anyio
async def test_async_generate_plan_proceeds_on_empty_input():
    """Scenario: AI-Driven Continuity (Proceed on Empty)"""
    from unittest.mock import AsyncMock, MagicMock

    mock_context = AsyncMock()
    mock_context_result = MagicMock()
    mock_context_result.header = "Header"
    mock_context_result.content = "Content"
    mock_context.async_get_context.return_value = mock_context_result

    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Corrected Plan"
    mock_response.model = "test-model"
    mock_llm.async_get_completion = AsyncMock(return_value=mock_response)
    mock_llm.get_completion_cost.return_value = 0.01
    mock_llm.get_token_count.return_value = 100

    mock_fs = MagicMock()
    mock_fs.path_exists.return_value = False  # No report.md
    mock_fs.read_file.return_value = ""  # Prevent MagicMock leakage into regex

    # Mock user interactor to return empty string
    mock_ui = AsyncMock()
    mock_ui.async_ask_question.return_value = ""

    from teddy_executor.core.domain.models.planning_ports import PlanningPorts
    from unittest.mock import AsyncMock, MagicMock

    mock_pm = MagicMock()
    mock_pm.async_resolve_message = AsyncMock(
        return_value="(No instructions provided. Please evaluate current state and proceed.)"
    )
    mock_pm.resolve_agent_metadata.return_value = ("pathfinder", {}, "meta.yaml")
    mock_pm.async_fetch_system_prompt = AsyncMock(return_value="system prompt")
    mock_pm.async_log_telemetry = AsyncMock(return_value=0.01)

    service = PlanningService(
        PlanningPorts(
            context=mock_context,
            llm=mock_llm,
            fs=mock_fs,
            config=MagicMock(),
            prompts=mock_pm,
            ui=mock_ui,
        )
    )

    # Act
    plan_path, _ = await service.async_generate_plan(
        user_message=None, turn_dir="sessions/20260417_120000-my-session/01"
    )

    # Assert: Should NOT return None
    assert plan_path is not None
    # Verify LLM was called (meaning it proceeded)
    mock_llm.async_get_completion.assert_called_once()
    # Verify default message was used
    call_args = mock_llm.async_get_completion.call_args
    messages = call_args.kwargs["messages"]
    user_content = messages[1]["content"]
    assert "(No instructions provided" in user_content


@pytest.mark.anyio
async def test_async_generate_plan_logs_sequenced_progress():
    """Scenario: Session Visibility & Natural Language Log Sequencing"""
    from unittest.mock import AsyncMock, MagicMock

    mock_context = AsyncMock()
    mock_context_result = MagicMock()
    mock_context_result.header = ""
    mock_context_result.content = ""
    mock_context.async_get_context.return_value = mock_context_result

    mock_llm = MagicMock()
    # Mocking response for persistence logic
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Plan"
    mock_llm.async_get_completion = AsyncMock(return_value=mock_response)

    mock_fs = MagicMock()
    mock_fs.path_exists.return_value = False
    mock_fs.read_file.return_value = ""

    mock_ui = AsyncMock()
    # Sequence: Resolve message (prompt) -> Display Log
    mock_ui.async_ask_question.return_value = "do something"

    from teddy_executor.core.domain.models.planning_ports import PlanningPorts
    from unittest.mock import AsyncMock, MagicMock

    mock_pm = MagicMock()
    mock_pm.async_resolve_message = AsyncMock(return_value="test message")
    mock_pm.resolve_agent_metadata.return_value = ("pathfinder", {}, "meta.yaml")
    mock_pm.async_fetch_system_prompt = AsyncMock(return_value="system prompt")
    mock_pm.async_log_telemetry = AsyncMock(return_value=0.01)

    service = PlanningService(
        PlanningPorts(
            context=mock_context,
            llm=mock_llm,
            fs=mock_fs,
            config=MagicMock(),
            prompts=mock_pm,
            ui=mock_ui,
        )
    )

    # Act
    await service.async_generate_plan(
        user_message=None, turn_dir="sessions/20260417_120000-fix-login-bug/02"
    )

    # Verify calls happened, filtering out boolean checks
    relevant_calls = [
        c
        for c in mock_ui.mock_calls
        if c[0] in ["async_ask_question", "async_display_message"]
    ]
    # PlanningService orchestrates message resolution via PromptManager.
    mock_pm.async_resolve_message.assert_called_once()

    # The interactor is used by PlanningService to display the planning log.
    assert any("Waiting for pathfinder to respond" in str(c) for c in relevant_calls)
