"""Regression tests pinning the startup banner spacing of `start` and `resume`.

Slice 00-38 unifies the spacing of the session-path line printed by
``handle_new_session`` and ``handle_resume_session``. These tests capture each
entry point's banner so the surrounding startup consolidation refactor cannot
silently change the spacing. They pin the CURRENT output: ``handle_new_session``
emits its session line with NO leading blank line, while ``handle_resume_session``
currently emits it WITH a leading blank line. The Logic deliverable of the slice
removes that leading blank and updates the resume expectation below.
"""

from pathlib import Path

from teddy_executor.adapters.inbound import session_cli_handlers as handlers
from teddy_executor.core.ports.inbound.init import IInitUseCase
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.ports.outbound.session_repository import ISessionRepository
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor


def _stub_startup_side_effects(monkeypatch) -> None:
    """Silence the background thread, health checks, and preflight gates.

    The banner is the only output under test, so every other startup side effect
    is replaced with a no-op.
    """
    monkeypatch.setattr(handlers, "find_project_root", lambda: Path("/fake/project"))
    monkeypatch.setattr(handlers, "background_check", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        handlers, "_display_update_notification", lambda container, cache_path: []
    )
    monkeypatch.setattr(handlers, "_run_health_checks", lambda: None)
    monkeypatch.setattr(
        handlers, "_run_cli_preflight_check", lambda container, **kwargs: []
    )
    monkeypatch.setattr(handlers, "_orchestrate_session_loop", lambda **kwargs: None)


def _model_config(env, model: str = "gpt-4o"):
    """Register an ``IConfigService`` mock whose ``llm.model`` resolves to ``model``."""
    mock_config = env.mock_port(IConfigService)
    mock_config.get_setting.side_effect = lambda key, default=None: (
        model if key == "llm.model" else default
    )
    return mock_config


def test_start_banner_session_line_has_no_leading_blank(env, monkeypatch, capsys):
    """`teddy start` prints the session path line directly beneath the identity block."""
    mock_session_manager = env.mock_port(ISessionManager)
    env.mock_port(IUserInteractor)
    env.mock_port(IInitUseCase)
    _model_config(env)
    mock_session_manager.create_session.return_value = "/fake/sessions/my-session"
    _stub_startup_side_effects(monkeypatch)

    handlers.handle_new_session(
        container=env.container,
        name=None,
        agent="pathfinder",
        interactive=False,
        no_copy=True,
        message="hi",
    )

    captured = capsys.readouterr()
    assert captured.out == "Session created at: /fake/sessions/my-session\n"
    assert (
        captured.err
        == "Checking configurations...\n\nAgent: Pathfinder\nModel: gpt-4o\n"
    )


def test_resume_banner_session_line_pins_current_spacing(env, monkeypatch, capsys):
    """`teddy resume` banner spacing is pinned before the consolidation refactor."""
    mock_session_manager = env.mock_port(ISessionManager)
    mock_repository = env.mock_port(ISessionRepository)
    _model_config(env)
    mock_session_manager.get_latest_turn.return_value = "/fake/sessions/my-session/01"
    mock_repository.load_meta.return_value = {}
    _stub_startup_side_effects(monkeypatch)
    monkeypatch.setattr(
        handlers, "_resolve_session_name", lambda container, path=None: "my-session"
    )

    handlers.handle_resume_session(container=env.container, path=None)

    captured = capsys.readouterr()
    assert captured.out == "\nResuming session: .teddy/sessions/my-session\n"
    assert captured.err == "Checking configurations...\n\nModel: gpt-4o\n"
