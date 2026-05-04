from pathlib import Path
from typing import Any, Dict, Optional, Sequence
from teddy_executor.core.ports.inbound.planning_use_case import IPlanningUseCase


class PlanningService(IPlanningUseCase):
    """
    Orchestrates context gathering and LLM interaction to generate plans.
    """

    from teddy_executor.core.domain.models.planning_ports import PlanningPorts

    def __init__(self, ports: PlanningPorts):
        self._context_service = ports.context
        self._llm_client = ports.llm
        self._file_system_manager = ports.fs
        self._config_service = ports.config
        self._prompt_manager = ports.prompts
        self._user_interactor = ports.ui

    def generate_plan(
        self,
        user_message: Optional[str],
        turn_dir: str,
        context_files: Optional[Dict[str, Sequence[str]]] = None,
    ) -> tuple[str, float]:
        """Generates a new plan.md file."""
        import re

        self._run_preflight_check()

        turn_path = Path(turn_dir)
        resolved_message = self._prompt_manager.resolve_message(user_message, turn_path)

        if resolved_message is None:
            return None, 0.0  # type: ignore

        agent_name, meta, meta_file_path = self._prompt_manager.resolve_agent_metadata(
            turn_path
        )

        if self._user_interactor:
            session_folder = turn_path.parent.name
            natural_name = re.sub(r"^\d{8}_\d{6}-", "", session_folder)
            msg = f"[cyan][{turn_path.name}] {natural_name} | Waiting for {agent_name} to respond...[/cyan]"
            self._user_interactor.display_message(msg)

        context = self._context_service.get_context(context_files=context_files)
        system_prompt = self._prompt_manager.fetch_system_prompt(agent_name, turn_path)

        # Scenario 1: Inject User Request into input.md on first turn
        header = context.header
        if turn_path.name == "01":
            user_request_block = (
                f"\n\n## User Request\n~~~~~~text\n{resolved_message}\n~~~~~~\n"
            )
            header = f"{context.header}{user_request_block}"

        full_context = f"{header}\n{context.content}"
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Context:\n{full_context}\n\nUser Message: {resolved_message}",
            },
        ]

        self._file_system_manager.write_file(
            (turn_path / "input.md").as_posix(), full_context
        )

        token_count = self._llm_client.get_token_count(messages=messages)

        # R-10-12: Implement retry loop for empty content (common with Gemini/LiteLLM safety blocks)
        max_retries = 3
        response = None
        plan_content = ""
        turn_cost = 0.0

        for attempt in range(max_retries):
            response = self._llm_client.get_completion(messages=messages)
            plan_content = self._extract_plan_content(response)
            turn_cost = self._llm_client.get_completion_cost(response)

            if plan_content and plan_content.strip():
                break

            if attempt < max_retries - 1:
                self._user_interactor.display_message(
                    f"[yellow]Empty response received (Attempt {attempt + 1}/{max_retries}). Retrying...[/yellow]"
                )

        cost_val = self._prompt_manager.log_telemetry(token_count, turn_cost)
        plan_path = (turn_path / "plan.md").as_posix()
        self._file_system_manager.write_file(plan_path, plan_content)
        self._prompt_manager.update_meta(
            meta, response, token_count, turn_cost, meta_file_path
        )

        return plan_path, cost_val

    def _run_preflight_check(self) -> None:
        """Ensures system is configured before attempting generation."""
        from teddy_executor.core.domain.models.exceptions import ConfigurationError

        errors = self._llm_client.validate_config()
        if not errors:
            return

        config_path = self._config_service.get_config_path()
        error_msg = (
            f"Configuration Error: {', '.join(errors)}\n"
            f"Please update your configuration at: {config_path}"
        )
        raise ConfigurationError(error_msg)

    def _extract_plan_content(self, response: Any) -> str:
        """Robustly extracts content from the LLM response object."""
        if hasattr(response, "choices") and len(response.choices) > 0:
            return getattr(response.choices[0].message, "content", "") or ""
        return ""
