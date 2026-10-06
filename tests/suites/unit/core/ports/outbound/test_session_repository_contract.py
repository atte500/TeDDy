"""Contract tests for the ISessionRepository outbound port."""

from teddy_executor.core.ports.outbound.session_repository import ISessionRepository


def test_port_declares_resolve_session_from_slug():
    """The port must declare slug-based resolution, mirroring path resolution."""
    assert hasattr(ISessionRepository, "resolve_session_from_slug"), (
        "ISessionRepository must declare resolve_session_from_slug"
    )
