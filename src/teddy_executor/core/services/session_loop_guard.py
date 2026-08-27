from typing import Optional

from teddy_executor.core.ports.outbound import IConfigService
from teddy_executor.core.ports.outbound.session_loop_guard import ISessionLoopGuard


class ProductionSessionLoopGuard(ISessionLoopGuard):
    """
    Production implementation: enforces YOLO guardrails in non-interactive mode.
    """

    def __init__(
        self,
        config_service: IConfigService,
        initial_turn: int,
        initial_cost: float,
    ) -> None:
        self._config_service = config_service
        self._initial_turn = initial_turn
        self._initial_cost = initial_cost

    def should_continue(
        self, turn_count: int, cumulative_cost: float, interactive: bool
    ) -> tuple[bool, Optional[str]]:
        if interactive:
            return True, None

        if not self._config_service.get_setting("yolo_guardrails.enabled", True):
            return True, None

        max_turns = int(
            self._config_service.get_setting("yolo_guardrails.max_turns", 99) or 99
        )
        max_cost = float(
            self._config_service.get_setting("yolo_guardrails.max_session_cost", 5.0)
            or 5.0
        )

        turn_delta = turn_count - self._initial_turn
        cost_delta = cumulative_cost - self._initial_cost

        if turn_delta >= max_turns:
            return False, "YOLO guardrail limit reached."

        if cost_delta >= max_cost:
            return False, "YOLO guardrail limit reached."

        return True, None
