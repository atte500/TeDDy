"""Regression: the bare ``teddy init`` CLI must confine its real filesystem
scaffolding to the current working directory.

A bare ``init`` unconditionally runs the real ``IInitUseCase.ensure_initialized()``,
which scaffolds ``.teddy/`` and ``docs/templates/``. ``LocalFileSystemAdapter``
resolves its default root (``"."``) lazily against the process CWD, so a test
that drives this command without changing CWD leaks ``docs/templates/`` into
the repo root and trips the session-scoped ``_assert_no_test_pollution``
Poka-Yoke (the macOS CI failure this regression guards against).

This test pins the observable confinement contract: given an isolated CWD, the
scaffold lands in that workspace and no ancestor directory is polluted.
"""

from typer.testing import CliRunner

import teddy_executor.__main__ as main_app


def test_bare_init_confines_scaffolding_to_cwd(tmp_path, monkeypatch, container):
    """``teddy init`` scaffolds into the CWD, never into a parent directory."""
    # The bare-init path resolves IInitUseCase from the global container; the
    # no-op patch keeps this test focused on filesystem confinement. The
    # `container` fixture supplies a fresh, real DI container (root_dir=".")
    # and restores the global container afterwards (no state leakage).
    monkeypatch.setattr(
        "teddy_executor.__main__._ensure_project_initialized",
        lambda container, root_dir=None: None,
    )

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    result = CliRunner().invoke(main_app.app, ["init"])

    assert result.exit_code == 0, result.stdout
    # The scaffold is confined to the isolated CWD ...
    assert (workspace / ".teddy").is_dir()
    assert (workspace / "docs" / "templates").is_dir()
    # ... and never leaks into a parent directory.
    assert not (tmp_path / ".teddy").exists()
    assert not (tmp_path / "docs").exists()
