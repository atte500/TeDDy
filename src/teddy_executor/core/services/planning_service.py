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
        self._session_manager = ports.session_manager

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

        self._persist_initial_request(resolved_message, turn_path)

        agent_name, meta, meta_file_path = self._prompt_manager.resolve_agent_metadata(
            turn_path
        )

        if self._user_interactor:
            session_folder = turn_path.parent.name
            natural_name = re.sub(r"^\d{8}_\d{6}-", "", session_folder)
            msg = f"\n[cyan][{turn_path.name}] {natural_name} | Waiting for {agent_name} to respond...[/cyan]"
            self._user_interactor.display_message(msg)

        context = self._context_service.get_context(
            context_files=context_files, agent_name=agent_name
        )
        system_prompt = self._prompt_manager.fetch_system_prompt(agent_name, turn_path)

        # Context is purely project state (including initial_request.md via session.context).
        full_context = f"{context.header}\n{context.content}"
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": full_context,
            },
        ]

        self._file_system_manager.write_file(
            (turn_path / "input.md").as_posix(), full_context
        )

        token_count = int(
            self._safe_float(self._llm_client.get_token_count(messages=messages))
        )

        if self._user_interactor:
            self._display_telemetry(meta, token_count)

        response, plan_content, turn_cost = self._perform_generation_with_retry(
            messages
        )

        cost_val = self._prompt_manager.log_telemetry(token_count, turn_cost)
        plan_path = (turn_path / "plan.md").as_posix()
        self._file_system_manager.write_file(plan_path, plan_content)
        self._prompt_manager.update_meta(
            meta, response, token_count, turn_cost, meta_file_path
        )

        return plan_path, cost_val

    def _persist_initial_request(self, message: str, turn_path: Path) -> None:
        """Pure Context Strategy: Persist instructions to the goal file."""
        if not message.strip():
            return

        request_path = (turn_path.parent / "initial_request.md").as_posix()
        self._file_system_manager.write_file(request_path, message)

        session_ctx = (turn_path.parent / "session.context").as_posix()
        if self._file_system_manager.path_exists(session_ctx):
            ctx_content = self._file_system_manager.read_file(session_ctx)
            if request_path not in ctx_content:
                new_ctx = f"{ctx_content.strip()}\n{request_path}\n"
                self._file_system_manager.write_file(session_ctx, new_ctx.lstrip())

    def _perform_generation_with_retry(
        self, messages: list[Dict[str, str]]
    ) -> tuple[Any, str, float]:
        """Implements retry loop for empty LLM content."""
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

            if attempt < max_retries - 1 and self._user_interactor:
                self._user_interactor.display_message(
                    f"[yellow]Empty response received (Attempt {attempt + 1}/{max_retries}). Retrying...[/yellow]"
                )

        return response, plan_content, turn_cost

    def _run_preflight_check(self) -> None:
        """Ensures system is configured before attempting generation."""
        from teddy_executor.core.domain.models.exceptions import ConfigurationError

        errors = self._llm_client.validate_config()
        if not errors:
            return

        error_msg = f"Configuration Error: {', '.join(errors)}"
        raise ConfigurationError(error_msg)

    def _extract_plan_content(self, response: Any) -> str:
        """Robustly extracts content from the LLM response object."""
        if hasattr(response, "choices") and len(response.choices) > 0:
            return getattr(response.choices[0].message, "content", "") or ""
        return ""

    def _display_telemetry(self, meta: Dict[str, Any], token_count: int) -> None:
        """Displays real-time telemetry about the upcoming LLM call."""
        model = str(
            meta.get("model")
            or self._config_service.get_setting("llm.model")
            or "gpt-4o"
        )
        context_window = self._safe_float(
            self._llm_client.get_context_window(model=model)
        )
        cumulative_cost = self._safe_float(meta.get("cumulative_cost"))

        self._user_interactor.display_message(
            f"[blue]• Model:[/blue] [magenta]{model}[/magenta]"
        )
        self._user_interactor.display_message(
            f"[blue]• Context:[/blue] [magenta]{token_count / 1000:.1f}k / {context_window / 1000:.1f}k tokens[/magenta]"
        )
        self._user_interactor.display_message(
            f"[blue]• Session Cost:[/blue] [magenta]${cumulative_cost:.4f}[/magenta]\n"
        )

    def _safe_float(self, v: Any, default: float = 0.0) -> float:
        """Robust conversion to float, handling mocks and strings."""
        try:
            if hasattr(v, "__float__"):
                return float(v)
            return float(str(v))
        except (TypeError, ValueError):
            return default
