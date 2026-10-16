from typing import Any, Optional

from teddy_executor.core.ports.outbound import IConfigService
from teddy_executor.core.ports.outbound.session_loop_guard import ISessionLoopGuard
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment


# Sentinel distinguishing "key absent" from a present falsy value, so the
# legacy `yolo_guardrails` namespace is consulted only when the renamed
# `guardrails` key is missing.
_UNSET = object()


class ProductionSessionLoopGuard(ISessionLoopGuard):
    """
    Production implementation: bounds a non-interactive run by turns and cost.
    """

    def __init__(  # noqa: PLR0913  # Explicit DI: config, environment, baselines, and CLI overrides.
        self,
        config_service: IConfigService,
        system_environment: ISystemEnvironment,
        initial_turn: int,
        initial_cost: float,
        max_turns: Optional[int] = None,
        max_cost: Optional[float] = None,
    ) -> None:
        self._config_service = config_service
        self._system_environment = system_environment
        self._initial_turn = initial_turn
        self._initial_cost = initial_cost
        # A CLI-supplied limit is the most specific source and wins outright.
        self._max_turns_override = max_turns
        self._max_cost_override = max_cost

    def _read_config(self, key: str, default: Any) -> Any:
        """Reads ``guardrails.<key>`` with a legacy ``yolo_guardrails`` fallback.

        Existing user configs still use the ``yolo_guardrails`` namespace, so
        when the renamed ``guardrails`` key is absent the legacy key is read
        before the default applies.
        """
        value = self._config_service.get_setting(f"guardrails.{key}", _UNSET)
        if value is _UNSET:
            value = self._config_service.get_setting(f"yolo_guardrails.{key}", _UNSET)
        return default if value is _UNSET else value

    def _resolve_limit(
        self,
        override: Optional[float],
        env_key: str,
        config_key: str,
        default: float,
    ) -> Any:
        """Resolves one limit through the precedence chain.

        Order: an explicit CLI override, then the environment variable, then the
        config value, then the default. The config value falls back to the
        default when it is absent or falsy; an explicit override of 0 still wins.
        """
        if override is not None:
            return override
        env_value = self._system_environment.get_env(env_key)
        if env_value:
            return env_value
        return self._read_config(config_key, default) or default

    def _resolve_max_turns(self) -> int:
        """Resolves the turn limit: CLI flag, then env var, then config, then 150."""
        return int(
            self._resolve_limit(
                self._max_turns_override, "TEDDY_MAX_TURNS", "max_turns", 150
            )
        )

    def _resolve_max_cost(self) -> float:
        """Resolves the cost limit: CLI flag, then env var, then config, then 5.0."""
        return float(
            self._resolve_limit(
                self._max_cost_override,
                "TEDDY_MAX_SESSION_COST",
                "max_session_cost",
                5.0,
            )
        )

    def should_continue(
        self, turn_count: int, cumulative_cost: float, interactive: bool
    ) -> tuple[bool, Optional[str]]:
        if interactive:
            return True, None

        if not bool(self._read_config("enabled", True)):
            return True, None

        max_turns = self._resolve_max_turns()
        max_cost = self._resolve_max_cost()

        turn_delta = turn_count - self._initial_turn
        cost_delta = cumulative_cost - self._initial_cost

        if turn_delta >= max_turns:
            config_path = self._config_service.get_config_path()
            import os as _os

            rel_path = _os.path.relpath(config_path)
            return False, (
                f"YOLO turn limit reached: {turn_delta}/{max_turns} turns in this run.\n"
                f"To change this limit, set 'guardrails.max_turns' in {rel_path}."
            )

        if cost_delta >= max_cost:
            config_path = self._config_service.get_config_path()
            import os as _os

            rel_path = _os.path.relpath(config_path)
            return False, (
                f"YOLO cost limit reached: ${cost_delta:.2f}/${max_cost:.2f} in this run.\n"
                f"To change this limit, set 'guardrails.max_session_cost' in {rel_path}."
            )

        return True, None

    def reset_baseline(self, turn_count: int, cumulative_cost: float) -> None:
        """Re-anchors both baselines after a message turn, when enabled.

        The reset is gated by ``guardrails.message_reset`` (default true), so an
        operator can keep the baselines fixed for the whole run.
        """
        if not bool(self._read_config("message_reset", True)):
            return
        self._initial_turn = turn_count
        self._initial_cost = cumulative_cost
