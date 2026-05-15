from teddy_executor.core.ports.outbound.session_loop_guard import ISessionLoopGuard


class ProductionSessionLoopGuard(ISessionLoopGuard):
    """
    Production implementation: always continues unless manually interrupted.
    """

    def should_continue(self, turn_count: int) -> bool:
        return True
