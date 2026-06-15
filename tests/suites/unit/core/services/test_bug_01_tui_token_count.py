"""
Regression test for Bug #01: TUI Token Count Shows 0.0k.

Verifies that PlanningService.generate_plan() propagates system_prompt_tokens
to the ProjectContext DTO after fetch_system_prompt() resolves the prompt text.
"""

from unittest.mock import MagicMock

from teddy_executor.core.domain.models.planning_ports import PlanningPorts
from teddy_executor.core.services.planning_service import PlanningService
from teddy_executor.core.domain.models.project_context import (
    ProjectContext,
    ContextItem,
)


class TestSystemPromptTokenPropagation:
    """Regression tests for system_prompt_tokens propagation."""

    def test_system_prompt_tokens_populated_after_fetch(self, env):
        """
        Verifies that after PlanningService.generate_plan() calls
        fetch_system_prompt(), the system prompt token count is computed
        and propagated to the ProjectContext DTO.

        Regression test for Bug #01: TUI Token Count Shows 0.0k
        """
        mock_context = MagicMock()
        mock_llm = MagicMock()
        mock_fs = MagicMock()
        mock_config = MagicMock()
        mock_prompts = MagicMock()
        mock_ui = MagicMock()
        mock_session = MagicMock()

        # Mock system prompt
        system_prompt_text = "You are a helpful assistant."
        mock_prompts.fetch_system_prompt.return_value = system_prompt_text
        mock_prompts.resolve_agent_metadata.return_value = (
            "developer",
            {"model": "gpt-4o", "turn_id": "01"},
            "/tmp/meta.yaml",
        )
        mock_prompts.resolve_message.return_value = "Generate a plan"
        mock_prompts.log_telemetry.return_value = 0.01

        # Mock LLM to return a known token count for the system prompt
        mock_llm.get_text_token_count.return_value = 95
        mock_llm.get_token_count.return_value = 500
        mock_llm.get_context_window.return_value = 128000
        mock_llm.supports_pricing.return_value = True
        mock_llm.get_completion_cost.return_value = 0.01
        mock_llm.validate_config.return_value = []

        # Mock config
        mock_config.get_setting.side_effect = lambda key, default=None: {
            "llm.model": "gpt-4o",
            "llm.max_retries": 3,
        }.get(key, default)

        # Mock session manager
        mock_session.resolve_context_paths.return_value = {"Default": []}

        # Create a ProjectContext with system_prompt_tokens=0 (bug state)
        returned_context = ProjectContext(
            header="test",
            content="test",
            items=[
                ContextItem(
                    path="src/main.py",
                    token_count=100,
                    git_status="M",
                    scope="Turn",
                    selected=True,
                ),
            ],
            agent_name="developer",
            system_prompt_tokens=0,  # BUG state: initialized to 0
            total_window=128000,
        )
        mock_context.get_context.return_value = returned_context

        # Mock file operations
        mock_fs.write_file.return_value = True
        mock_fs.path_exists.return_value = True
        mock_fs.read_file.return_value = ""

        # Mock LLM response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "## Plan\nTest plan"
        mock_response.model = "gpt-4o"
        mock_llm.get_completion.return_value = mock_response

        ports = PlanningPorts(
            context=mock_context,
            llm=mock_llm,
            fs=mock_fs,
            config=mock_config,
            prompts=mock_prompts,
            ui=mock_ui,
            session_manager=mock_session,
        )

        service = PlanningService(ports=ports)

        try:
            service.generate_plan(
                user_message="Test",
                turn_dir="/tmp/test_session/01",
            )
        except Exception:
            pass  # Expected with mock environment

        # ASSERT: system_prompt_tokens should be populated after fetch_system_prompt()
        # Before the fix, this was 0. After the fix, it should be 95.
        assert returned_context.system_prompt_tokens > 0, (
            f"Expected system_prompt_tokens > 0, got {returned_context.system_prompt_tokens}. "
            "Bug #01 regression: system prompt token count was not propagated to ProjectContext."
        )
        assert returned_context.system_prompt_tokens == 95, (
            f"Expected system_prompt_tokens == 95, got {returned_context.system_prompt_tokens}"
        )

        # Verify get_text_token_count was called with the system prompt text and model
        mock_llm.get_text_token_count.assert_called_once_with(
            system_prompt_text, model="gpt-4o"
        )
