"""Regression test: resume -a/--agent override is shown in the identity banner.

Bug 07 (resume-agent-override): `teddy resume -a prototyper` displayed the
session's STORED agent (`Agent: Pathfinder`) instead of the requested override
because the `-a/--agent` value was never threaded into the display path.

These tests pin the override-vs-persisted contract: the banner reflects the
EFFECTIVE agent (the override when provided, else the stored `meta.yaml` value).
"""

from unittest.mock import MagicMock  # noqa: TID251

from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.ports.outbound.session_repository import ISessionRepository

STORED_AGENT = "pathfinder"
SESSION_NAME = "20250101_120000-test-session"


def _build_container() -> MagicMock:
    """Minimal container mock wired for the resume display path."""
    container = MagicMock()
    mock_repo = MagicMock(spec=ISessionRepository)
    mock_session_manager = MagicMock(spec=ISessionManager)
    mock_fs = MagicMock(spec=IFileSystemManager)
    mock_config = MagicMock()
    mock_llm = MagicMock()
    mock_llm.validate_config.return_value = []

    mock_config.get_setting.side_effect = lambda key, default=None: {
        "llm.model": "openrouter/config-model",
    }.get(key, default)
    mock_session_manager.get_latest_session_name.side_effect = ValueError(
        "No path provided"
    )
    mock_session_manager.get_cumulative_cost.return_value = 0.0
    mock_config.get_config_path.return_value = ".teddy/config.yaml"

    mock_repo.load_meta.return_value = {
        "model": "stored-model",
        "agent_name": STORED_AGENT,
    }
    mock_session_manager.get_latest_turn.return_value = (
        f".teddy/sessions/{SESSION_NAME}/01"
    )
    mock_session_manager.resolve_session_from_path.return_value = SESSION_NAME

    container.resolve.side_effect = lambda cls, **kw: {
        ISessionManager: mock_session_manager,
        ISessionRepository: mock_repo,
        IFileSystemManager: mock_fs,
        ILlmClient: mock_llm,
        IConfigService: mock_config,
    }.get(cls, MagicMock())
    return container


def _neutralize_boundaries(monkeypatch) -> None:
    """Patch the network / side-effecting boundaries for a deterministic run."""
    from teddy_executor.adapters.inbound import session_cli_handlers as handlers

    monkeypatch.setattr(handlers, "background_check", lambda *a, **k: None)
    monkeypatch.setattr(handlers, "_display_update_notification", lambda *a, **k: [])
    monkeypatch.setattr(handlers, "_run_health_checks", lambda *a, **k: None)
    monkeypatch.setattr(handlers, "_run_cli_preflight_check", lambda *a, **k: [])
    monkeypatch.setattr(handlers, "_orchestrate_session_loop", MagicMock())


def test_resume_agent_override_is_shown_in_banner(monkeypatch, capsys):
    """`resume -a prototyper` shows `Agent: Prototyper`, not the stored agent."""
    from teddy_executor.adapters.inbound import session_cli_handlers as handlers

    _neutralize_boundaries(monkeypatch)
    container = _build_container()

    handlers.handle_resume_session(
        container=container,
        path="test-session",
        interactive=False,
        no_copy=True,
        agent="prototyper",
    )

    captured = capsys.readouterr()
    assert "Agent: Prototyper" in captured.err, (
        f"Expected the -a override in the banner, got: {captured.err.strip()!r}"
    )
    assert "Agent: Pathfinder" not in captured.err, (
        "The banner must not display the stored agent when -a overrides it."
    )


def test_resume_without_override_shows_stored_agent(monkeypatch, capsys):
    """Without `-a`, the banner falls back to the stored `meta.yaml` agent."""
    from teddy_executor.adapters.inbound import session_cli_handlers as handlers

    _neutralize_boundaries(monkeypatch)
    container = _build_container()

    handlers.handle_resume_session(
        container=container,
        path="test-session",
        interactive=False,
        no_copy=True,
    )

    captured = capsys.readouterr()
    assert "Agent: Pathfinder" in captured.err, (
        f"Expected the stored agent in the banner, got: {captured.err.strip()!r}"
    )
