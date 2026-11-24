from pathlib import Path
from typing import Any, Dict, Optional, Sequence
from teddy_executor.core.domain.models import ProjectContext
from teddy_executor.core.domain.models.config_schema import (
    resolve_agent_llm_overrides,
    resolve_effective_model,
)
from teddy_executor.core.ports.inbound.planning_use_case import IPlanningUseCase
from teddy_executor.core.utils.interruptible_call import run_interruptible


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
    ) -> tuple[str, float, ProjectContext]:
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

        # One resolution feeds both the effective model and the completion
        # overlay, so the two can never disagree. An absent persona block yields
        # an empty overlay, leaving the global ``llm`` path unchanged.
        llm_overrides = resolve_agent_llm_overrides(
            self._config_service.get_setting("agents", {}), agent_name
        )

        # The explicit ``--model`` flag (carried as ``model_override``) wins,
        # then the persona entry, then the global default. The carried ``model``
        # key is display data only and never a resolution input, so a persona
        # switched on resume re-resolves every turn.
        model = resolve_effective_model(
            meta.get("model_override"),
            llm_overrides.get("model"),
            self._config_service.get_setting("llm.model"),
        )
        try:
            system_token_count = self._llm_client.get_text_token_count(
                system_prompt, model=model
            )
        except Exception:
            system_token_count = 0

        session_root = str(Path(turn_dir).parent)
        context = self._context_service.get_context(
            context_files=resolved_context_files,
            agent_name=agent_name,
            current_turn=Path(turn_dir).name,
            system_prompt_tokens=system_token_count,
            cache_dir=session_root,
            session_root=session_root,
            model=model,
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

        response, token_count, plan_content, turn_cost = run_interruptible(
            lambda: self._run_planning_phase(messages, model, meta, llm_overrides)
        )

        # Persist the explicit recorded-cost signal (Option B): a real price was
        # used for this turn whenever the adapter marked the response, so a
        # later turn can show the accumulated figure even for an unpriced model.
        # The `is True` guard keeps an auto-specced Mock response from counting.
        if getattr(response, "_teddy_cost_recorded", False) is True:
            meta["cost_recorded"] = True

        cost_val = self._prompt_manager.log_telemetry(token_count, turn_cost)
        plan_path = (turn_path / "plan.md").as_posix()
        self._file_system_manager.write_file(plan_path, plan_content)
        # Pre-populate meta["model"] before update_meta to ensure the user-configured
        # model (with routing prefix like openrouter/) is preserved.
        # This prevents the bug where meta["model"] was missing on first turn (no --model flag)
        # and update_meta overwrote it with the bare actual model.
        meta.setdefault("model", model)
        # Provider cache accounting is read from the response the cost lookup
        # already inspected; an uninstrumented client reports zeros.
        token_usage = self._llm_client.get_token_usage(response)
        self._prompt_manager.update_meta(
            meta,
            response,
            token_count,
            turn_cost,
            meta_file_path,
            token_usage=token_usage,
        )

        return plan_path, cost_val, context

    def _run_planning_phase(
        self,
        messages: list[Dict[str, str]],
        model: str,
        meta: Dict[str, Any],
        llm_overrides: Optional[Dict[str, Any]] = None,
    ) -> tuple[Any, int, str, float]:
        """Perform every blocking planning call on the interruptible worker.

        Hydration, the token count, telemetry, the budget check, and the
        completion all touch the network. The main thread waits on this worker's
        future, so a quit interrupts the wait instead of the raw socket read.
        """
        # Pre-emptive Hydration: Trigger hydration via get_context_window BEFORE counting tokens.
        # This ensures the model is known to the registry so token counting and telemetry work.
        if self._user_interactor:
            # We call this for the side-effect of triggering hydration in Turn 1
            self._llm_client.get_context_window(model=model)

        token_count = int(
            self._safe_float(
                self._llm_client.get_token_count(messages=messages, model=model)
            )
        )

        if self._user_interactor:
            self._display_telemetry(meta, token_count, model)

        self._check_context_budget(token_count, model)

        response, plan_content, turn_cost = self._perform_generation_with_retry(
            messages,
            model=model,
            llm_overrides=llm_overrides,
        )
        return response, token_count, plan_content, turn_cost

    def _perform_generation_with_retry(
        self,
        messages: list[Dict[str, str]],
        model: str,
        llm_overrides: Optional[Dict[str, Any]] = None,
    ) -> tuple[Any, str, float]:
        """Implements retry loop for empty LLM content."""
        max_retries_val = self._config_service.get_setting("llm.max_retries")
        max_retries = int(max_retries_val) if max_retries_val is not None else 3
        response = None
        plan_content = ""
        turn_cost = 0.0

        for attempt in range(max_retries):
            # The overlay key is added only when the persona configures one, so a
            # project without an ``agents`` block issues the same call shape as
            # before this feature existed.
            completion_kwargs: Dict[str, Any] = {"messages": messages, "model": model}
            if llm_overrides:
                completion_kwargs["llm_overrides"] = llm_overrides
            response = self._llm_client.get_completion(**completion_kwargs)
            plan_content = self._extract_plan_content(response)
            attempt_cost = self._llm_client.get_completion_cost(
                response, model_override=model
            )
            turn_cost += attempt_cost

            if plan_content and plan_content.strip():
                break

            if attempt < max_retries - 1 and self._user_interactor:
                self._user_interactor.display_message(
                    f"[yellow]Empty response received (Attempt {attempt + 1}/{max_retries}). Retrying...[/yellow]"
                )

        return response, plan_content, turn_cost

    def _run_preflight_check(self) -> None:
        """Ensures system is configured before attempting generation.

        Validation runs on every turn, so a persona switched mid-session is
        always checked against the active configuration. There is deliberately
        no process-wide preflight cache: a cache keyed on nothing would only
        suppress re-validating a different persona, and the local check is cheap.
        """
        from teddy_executor.core.domain.models.exceptions import ConfigurationError

        # Perform local validation only. Remote connectivity is checked lazily
        # by the LLM client during actual generation. This ensures fast CLI startup
        # and eliminates redundant remote lag for sessions.
        errors = self._llm_client.validate_config(include_remote=False)

        if errors:
            error_msg = f"Configuration Error: {', '.join(errors)}"
            raise ConfigurationError(error_msg)

    def _extract_plan_content(self, response: Any) -> str:
        """Robustly extracts content from the LLM response object."""
        if hasattr(response, "choices") and len(response.choices) > 0:
            return getattr(response.choices[0].message, "content", "") or ""
        return ""

    def _display_telemetry(
        self,
        meta: Dict[str, Any],
        token_count: int,
        effective_model: Optional[str] = None,
    ) -> None:
        """Displays real-time telemetry about the upcoming LLM call.

        The served ``actual_model`` wins for an already-answered turn, then the
        carried ``model`` (display data), then the freshly resolved effective
        model. The ordering keeps a fresh turn's banner on the effective model
        without disturbing an existing display value.
        """
        model = str(
            meta.get("actual_model")
            or meta.get("model")
            or effective_model
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
        # Option B: gate on an explicit recorded-cost signal, never on
        # `cumulative_cost > 0`, because a free model legitimately records 0.0
        # and cannot be distinguished from "no cost" by cost > 0.
        cost_recorded = meta.get("cost_recorded") is True
        show_cost = context_window > 0 and (pricing_supported or cost_recorded)
        cost_str = f"${cumulative_cost:.4f}" if show_cost else "$???"

        cumulative_prompt = int(self._safe_float(meta.get("cumulative_prompt_tokens")))
        cumulative_cached = int(self._safe_float(meta.get("cumulative_cached_tokens")))
        cached_suffix = ""
        if (
            show_cost
            and cumulative_cost > 0
            and cumulative_prompt > 0
            and cumulative_cached > 0
        ):
            pct = min(100, round(cumulative_cached * 100 / cumulative_prompt))
            cached_suffix = f" ({pct}% cached)"

        self._user_interactor.display_message(
            f"[blue]• Session Cost:[/blue] [magenta]{cost_str}{cached_suffix}"
            "[/magenta]\n"
        )

    def _check_context_budget(self, token_count: int, model: str) -> None:
        """Raise a user-visible error when the request exceeds the model window.

        Case file 07 Measure 2 (Jidoka): the request token count and the model
        context window were computed only for display. This turns an oversized
        request into a loud failure instead of a silent stall inside the LLM
        call. A non-positive window means the window is unknown, so no error is
        raised and only a strict excess is over budget.
        """
        from teddy_executor.core.domain.models.exceptions import ConfigurationError

        context_window = int(
            self._safe_float(self._llm_client.get_context_window(model=model))
        )
        if context_window > 0 and token_count > context_window:
            raise ConfigurationError(
                f"Context Window Exceeded: the request is {token_count} tokens, "
                f"which exceeds the {context_window}-token context window of "
                f"model '{model}'."
            )

    def _safe_float(self, v: Any, default: float = 0.0) -> float:
        """Robust conversion to float, handling mocks and strings."""
        try:
            if hasattr(v, "__float__"):
                return float(v)
            return float(str(v))
        except (TypeError, ValueError):
            return default
