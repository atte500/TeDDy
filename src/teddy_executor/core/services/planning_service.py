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

        turn_path = Path(turn_dir)
        agent_name, meta, meta_file_path = self._prompt_manager.resolve_agent_metadata(
            turn_path
        )

        if self._user_interactor:
            session_folder = turn_path.parent.name
            natural_name = re.sub(r"^\d{8}_\d{6}-", "", session_folder)
            msg = f"\n[cyan][{turn_path.name}] {natural_name} | Waiting for {agent_name} to respond...[/cyan]"
            self._user_interactor.display_message(msg)

        self._run_preflight_check()

        # Defensive resolution of context manifests from turn_dir
        resolved_context_files = context_files
        if resolved_context_files is None and self._session_manager:
            plan_path = (turn_path / "plan.md").as_posix()
            # Mypy: dict is invariant, so dict[str, list] != dict[str, Sequence]
            resolved_context_files = self._session_manager.resolve_context_paths(  # type: ignore[assignment]
                plan_path
            )
        # Resolve message to capture user intent in meta.yaml
        resolved_message = self._prompt_manager.resolve_message(user_message, turn_path)

        if resolved_message is not None:
            if not meta.get("is_replan"):
                meta["user_request"] = resolved_message

        system_prompt = self._prompt_manager.fetch_system_prompt(agent_name, turn_path)

        # Compute system prompt token count BEFORE context construction so the
        # ProjectContext DTO is born with correct data (no post-hoc patching needed).
        model = str(
            meta.get("model") or self._config_service.get_setting("llm.model") or ""
        )
        try:
            system_token_count = self._llm_client.get_text_token_count(
                system_prompt, model=model
            )
        except Exception:
            system_token_count = 0

        context = self._context_service.get_context(
            context_files=resolved_context_files,
            agent_name=agent_name,
            current_turn=Path(turn_dir).name,
            system_prompt_tokens=system_token_count,
        )

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

        model = str(
            meta.get("model") or self._config_service.get_setting("llm.model") or ""
        )

        # Pre-emptive Hydration: Trigger hydration via get_context_window BEFORE counting tokens.
        # This ensures the model is known to the registry so token counting and telemetry work.
        if self._user_interactor:
            # We call this for the side-effect of triggering hydration in Turn 1
            self._llm_client.get_context_window(model=model)

        token_count = int(
            self._safe_float(self._llm_client.get_token_count(messages=messages))
        )

        if self._user_interactor:
            self._display_telemetry(meta, token_count)

        response, plan_content, turn_cost = self._perform_generation_with_retry(
            messages,
            model=model,
            provider=meta.get("provider"),
            api_key=meta.get("api_key"),
        )

        cost_val = self._prompt_manager.log_telemetry(token_count, turn_cost)
        plan_path = (turn_path / "plan.md").as_posix()
        self._file_system_manager.write_file(plan_path, plan_content)
        # Pre-populate meta["model"] before update_meta to ensure the user-configured
        # model (with routing prefix like openrouter/) is preserved.
        # This prevents the bug where meta["model"] was missing on first turn (no --model flag)
        # and update_meta overwrote it with the bare actual model.
        meta.setdefault("model", model)
        self._prompt_manager.update_meta(
            meta, response, token_count, turn_cost, meta_file_path
        )

        return plan_path, cost_val

    def _perform_generation_with_retry(
        self,
        messages: list[Dict[str, str]],
        model: str,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> tuple[Any, str, float]:
        """Implements retry loop for empty LLM content."""
        max_retries_val = self._config_service.get_setting("llm.max_retries")
        max_retries = int(max_retries_val) if max_retries_val is not None else 3
        response = None
        plan_content = ""
        turn_cost = 0.0

        # Construct overrides dict for kwargs
        overrides = {}
        if provider:
            overrides["provider"] = provider
        if api_key:
            overrides["api_key"] = api_key

        for attempt in range(max_retries):
            response = self._llm_client.get_completion(
                messages=messages, model=model, **overrides
            )
            plan_content = self._extract_plan_content(response)
            turn_cost = self._llm_client.get_completion_cost(
                response, model_override=model
            )

            if plan_content and plan_content.strip():
                break

            if attempt < max_retries - 1 and self._user_interactor:
                self._user_interactor.display_message(
                    f"[yellow]Empty response received (Attempt {attempt + 1}/{max_retries}). Retrying...[/yellow]"
                )

        return response, plan_content, turn_cost

    # Class-level cache to ensure remote preflight is performed exactly once per process.
    # This eliminates the 10s timeout lag on subsequent turns in a session.
    _PREFLIGHT_DONE = False

    @classmethod
    def reset_preflight(cls) -> None:
        """Resets the preflight cache (used primarily for testing)."""
        cls._PREFLIGHT_DONE = False

    def _run_preflight_check(self) -> None:
        """Ensures system is configured before attempting generation."""
        from teddy_executor.core.domain.models.exceptions import ConfigurationError

        # Perform local validation only. Remote connectivity is checked lazily
        # by the LLM client during actual generation. This ensures fast CLI startup
        # and eliminates redundant remote lag for sessions.
        errors = self._llm_client.validate_config(include_remote=False)

        if not errors:
            PlanningService._PREFLIGHT_DONE = True
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
            meta.get("actual_model")
            or meta.get("model")
            or self._config_service.get_setting("llm.model")
            or "unknown"
        )
        context_window = self._safe_float(
            self._llm_client.get_context_window(model=model)
        )
        cumulative_cost = self._safe_float(meta.get("cumulative_cost"))

        self._user_interactor.display_message(
            f"[blue]• Model:[/blue] [magenta]{model}[/magenta]"
        )

        window_str = f"{context_window / 1000:.1f}k" if context_window > 0 else "???"
        self._user_interactor.display_message(
            f"[blue]• Context:[/blue] [magenta]{token_count / 1000:.1f}k / {window_str} tokens[/magenta]"
        )

        pricing_supported = self._llm_client.supports_pricing(model=model)
        cost_str = (
            f"${cumulative_cost:.4f}"
            if context_window > 0 and pricing_supported
            else "$???"
        )
        self._user_interactor.display_message(
            f"[blue]• Session Cost:[/blue] [magenta]{cost_str}[/magenta]\n"
        )

    def _safe_float(self, v: Any, default: float = 0.0) -> float:
        """Robust conversion to float, handling mocks and strings."""
        try:
            if hasattr(v, "__float__"):
                return float(v)
            return float(str(v))
        except (TypeError, ValueError):
            return default
