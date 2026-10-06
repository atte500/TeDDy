"""Unit tests for the ``_resolve_session_name`` slug fallback (Slice 00-30).

The slug fallback is wired in the CLI adapter (``_resolve_session_name``): a
supplied ``path`` is resolved path-first and, ONLY on ``ValueError``, falls back
to slug resolution. These tests lock that contract in at the unit layer and prove
the no-``path`` (CWD-climb → ``get_latest_session_name``) branch is unchanged.
"""

from pathlib import Path
from unittest.mock import create_autospec

from teddy_executor.adapters.inbound.session_cli_handlers import _resolve_session_name
from teddy_executor.core.ports.outbound.session_manager import ISessionManager


class _ContainerStub:
    """Minimal container stub that resolves ISessionManager to an injected double."""

    def __init__(self, session_manager):
        self._session_manager = session_manager

    def resolve(self, port):
        assert port is ISessionManager, f"Unexpected port resolved: {port}"
        return self._session_manager


def _make_container():
    session_manager = create_autospec(ISessionManager, instance=True)
    return _ContainerStub(session_manager), session_manager


def test_resolve_session_name_falls_back_to_slug_when_path_fails():
    # Arrange: path resolution fails, slug resolution succeeds.
    container, session_manager = _make_container()
    session_manager.resolve_session_from_path.side_effect = ValueError(
        "Could not resolve session from path: add-user-auth"
    )
    session_manager.resolve_session_from_slug.return_value = (
        "20260124_153000-add-user-auth"
    )

    # Act
    resolved = _resolve_session_name(container, "add-user-auth")

    # Assert: the path is tried first, then the slug fallback is used verbatim.
    session_manager.resolve_session_from_path.assert_called_once_with("add-user-auth")
    session_manager.resolve_session_from_slug.assert_called_once_with("add-user-auth")
    assert resolved == "20260124_153000-add-user-auth"


def test_resolve_session_name_does_not_fall_back_when_path_resolves():
    # Arrange: path resolution succeeds.
    container, session_manager = _make_container()
    session_manager.resolve_session_from_path.return_value = (
        "20260124_153000-add-user-auth"
    )

    # Act
    resolved = _resolve_session_name(
        container, ".teddy/sessions/20260124_153000-add-user-auth"
    )

    # Assert: slug resolution is never attempted when the path resolves.
    session_manager.resolve_session_from_path.assert_called_once_with(
        ".teddy/sessions/20260124_153000-add-user-auth"
    )
    session_manager.resolve_session_from_slug.assert_not_called()
    assert resolved == "20260124_153000-add-user-auth"


def test_resolve_session_name_without_path_uses_cwd_then_latest():
    # Arrange: no path supplied; CWD-climb fails, latest-session fallback succeeds.
    container, session_manager = _make_container()
    session_manager.resolve_session_from_path.side_effect = ValueError(
        "Could not resolve session from path: /some/cwd"
    )
    session_manager.get_latest_session_name.return_value = (
        "20260124_153000-add-user-auth"
    )

    # Act
    resolved = _resolve_session_name(container, None)

    # Assert: the no-path branch climbs from the CWD and never touches slug resolution.
    session_manager.resolve_session_from_path.assert_called_once_with(
        str(Path.cwd().resolve())
    )
    session_manager.resolve_session_from_slug.assert_not_called()
    session_manager.get_latest_session_name.assert_called_once_with()
    assert resolved == "20260124_153000-add-user-auth"
