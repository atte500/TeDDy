from pathlib import Path
from typing import Optional

from teddy_executor.core.domain.models import ExecutionReport
from teddy_executor.core.ports.outbound.session_manager import (
    ISessionManager,
    SessionState,
)


class DummyManager:
    """A dummy implementation that satisfies the ISessionManager protocol."""

    def create_session(
        self,
        name: str,
        agent_name: str,
        initial_request: Optional[str] = None,
        additional_context: Optional[list[str]] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> str:
        return "ok"

    def get_latest_turn(self, _session_name: str) -> str:
        return ""

    def get_session_state(self, session_name: str) -> tuple[SessionState, str]:
        return SessionState.EMPTY, ""

    def transition_to_next_turn(
        self,
        plan_path: str,
        execution_report: Optional[ExecutionReport] = None,
        turn_cost: float = 0.0,
        is_validation_failure: bool = False,
        pruned_paths: Optional[list[str]] = None,
    ) -> str:
        return ""

    def resolve_context_paths(self, plan_path: str) -> dict[str, list[str]]:
        return {}

    def rename_session(self, old_name: str, new_name: str) -> str:
        return ""

    def get_latest_session_name(self) -> str:
        return ""

    def resolve_session_from_path(self, path: str) -> str:
        return ""

    def to_root_relative(self, turn_dir: Path, filename: str) -> str:
        return ""


def test_session_manager_contract_accepts_new_parameters():
    """Assert that the ISessionManager protocol now defines the expanded signature."""
    assert isinstance(DummyManager(), ISessionManager)


def test_session_manager_contract_rejects_partial_implementation():
    """Assert that a class missing required methods fails Protocol check."""

    class PartialManager:
        def create_session(
            self,
            name: str,
            agent_name: str,
            initial_request: Optional[str] = None,
            additional_context: Optional[list[str]] = None,
        ) -> str:
            return "ok"

    assert not isinstance(PartialManager(), ISessionManager)
