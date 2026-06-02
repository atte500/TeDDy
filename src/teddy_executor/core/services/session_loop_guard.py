from teddy_executor.core.ports.outbound import IConfigService
from teddy_executor.core.ports.outbound.session_loop_guard import ISessionLoopGuard


class ProductionSessionLoopGuard(ISessionLoopGuard):
    """
    Production implementation: always continues unless manually interrupted.
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
    ) -> bool:
        return True
