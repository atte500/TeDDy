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

    service = PlanningService(
        context_service=mock_context,
        llm_client=mock_llm,
        file_system_manager=MagicMock(),
        config_service=MagicMock(),
    )

    # Act: Execute the now-implemented method
    plan_path, cost = await service.async_generate_plan(
        user_message="test", turn_dir="test_dir"
    )

    # Assert: Method successfully generates a plan (proves implementation exists)
    assert plan_path is not None
    assert cost == 0.01


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

    service = PlanningService(
        context_service=mock_context,
        llm_client=mock_llm,
        file_system_manager=mock_fs,
        config_service=MagicMock(),
        user_interactor=mock_ui,
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
    from unittest.mock import AsyncMock, MagicMock, call

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

    service = PlanningService(
        context_service=mock_context,
        llm_client=mock_llm,
        file_system_manager=mock_fs,
        config_service=MagicMock(),
        user_interactor=mock_ui,
    )

    # Act
    await service.async_generate_plan(
        user_message=None, turn_dir="sessions/20260417_120000-fix-login-bug/02"
    )

    # Assert: Natural name used, prefix stripped, sequenced correctly
    expected_log = (
        "[cyan][02] fix-login-bug | Waiting for pathfinder to respond...[/cyan]"
    )

    # Verify calls happened in order, filtering out boolean checks
    relevant_calls = [
        c
        for c in mock_ui.mock_calls
        if c[0] in ["async_ask_question", "async_display_message"]
    ]
    assert relevant_calls[0] == call.async_ask_question(
        "Enter your instructions for the AI"
    )
    assert relevant_calls[1] == call.async_display_message(expected_log)
