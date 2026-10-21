"""Unit tests pinning the shared startup helpers extracted by Slice 00-38.

Slice 00-38 consolidates the duplicated session-startup preamble and the
identical error handler so ``handle_new_session`` and ``handle_resume_session``
cannot drift apart. These tests pin the routing (both entry points drive startup
through the same module-level helpers) and the shared error-handler contract.
"""

import pytest
import typer

from teddy_executor.adapters.inbound import session_cli_handlers as handlers
from teddy_executor.core.domain.models.exceptions import ConfigurationError
from teddy_executor.core.ports.inbound.init import IInitUseCase
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor


def _stub_handler_collaborators(env, monkeypatch, record):
    """Replace the shared helpers and every non-shared collaborator.

    The shared helpers are the subject under test, so they are replaced by
    recorders while the surrounding side effects (session creation, planning
    loop, identity banner, session meta) are stubbed to no-ops.
    """
    mock_session_manager = env.mock_port(ISessionManager)
    mock_session_manager.create_session.return_value = "/fake/sessions/my-session"
    env.mock_port(IUserInteractor)
    env.mock_port(IInitUseCase)

    def record_background(container):
        record.setdefault("background", []).append(container)
        return []

    def record_preamble(container, fired, **kwargs):
        record.setdefault("preamble", []).append(kwargs)

    monkeypatch.setattr(handlers, "_start_background_update_check", record_background)
    monkeypatch.setattr(handlers, "_run_startup_preamble", record_preamble)
    monkeypatch.setattr(
        handlers, "_pull_workspace_on_start", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(handlers, "_echo_config_success", lambda *args, **kwargs: None)
    monkeypatch.setattr(handlers, "_orchestrate_session_loop", lambda **kwargs: None)
    monkeypatch.setattr(
        handlers, "_resolve_session_name", lambda container, path=None: "my-session"
    )
    monkeypatch.setattr(
        handlers, "_sync_and_display_session_meta", lambda *args, **kwargs: None
    )


def test_both_handlers_route_startup_through_shared_helpers(env, monkeypatch):
    """Both entry points drive startup through the same shared helpers."""
    record = {}
    _stub_handler_collaborators(env, monkeypatch, record)

    handlers.handle_new_session(
        container=env.container,
        name=None,
        agent="developer",
        interactive=False,
        no_copy=True,
        message="hi",
    )
    handlers.handle_resume_session(container=env.container, path=None)

    assert len(record["background"]) == 2
    assert len(record["preamble"]) == 2
    # `start` forwards its agent to the preflight; `resume` leaves it unset.
    assert record["preamble"][0]["agent"] == "developer"
    assert record["preamble"][1].get("agent") is None


def test_start_routes_startup_failure_through_shared_error_handler(env, monkeypatch):
    """A startup failure in `start` is delegated to the shared error handler."""
    env.mock_port(IInitUseCase)
    handled = []

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        handlers, "_start_background_update_check", lambda container: []
    )
    monkeypatch.setattr(handlers, "_run_startup_preamble", boom)
    monkeypatch.setattr(
        handlers,
        "_handle_startup_error",
        lambda container, error: handled.append(error),
    )

    handlers.handle_new_session(
        container=env.container,
        name=None,
        agent="pathfinder",
        interactive=False,
        no_copy=True,
        message="hi",
    )

    assert len(handled) == 1
    assert str(handled[0]) == "boom"


def test_shared_error_handler_prints_config_hint_for_configuration_error(env, capsys):
    """A ConfigurationError prints the error plus the configuration path hint."""
    mock_config = env.mock_port(IConfigService)
    mock_config.get_config_path.return_value = ".teddy/config.yaml"

    with pytest.raises(typer.Exit) as excinfo:
        handlers._handle_startup_error(env.container, ConfigurationError("bad config"))

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "Error: bad config" in captured.err
    assert "Please update your configuration at: .teddy/config.yaml" in captured.err


def test_shared_error_handler_prints_plain_error_for_generic_exception(env, capsys):
    """A generic exception prints only the error line."""
    with pytest.raises(typer.Exit) as excinfo:
        handlers._handle_startup_error(env.container, RuntimeError("boom"))

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert captured.err == "Error: boom\n"
