"""Unit tests: the turn-scoped execution-started marker filename is single-sourced."""

from teddy_executor.core.ports.outbound.session_manager import (
    EXECUTION_STARTED_MARKER,
)


def test_execution_started_marker_names_the_turn_marker_file() -> None:
    assert EXECUTION_STARTED_MARKER == "execution.started"
