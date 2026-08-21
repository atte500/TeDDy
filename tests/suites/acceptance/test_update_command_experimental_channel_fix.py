"""Regression test for Bug #20: experimental channel shows wrong upgrade command.

When current is a prerelease (TestPyPI channel) and latest is a strictly newer
stable, `teddy update` (without --experimental) should show:
    uv tool install teddy-cli --force

Previously it showed:
    uv tool upgrade teddy-cli
"""

import typer.testing

from teddy_executor.__main__ import app


runner = typer.testing.CliRunner()


def test_prerelease_current_with_newer_stable_shows_force_install(monkeypatch):
    """Bug #20: Current prerelease (0.1.5.dev646) < latest stable (0.1.5).
    Expected: 'uv tool install teddy-cli --force'
    Actual (before fix): 'uv tool upgrade teddy-cli'
    """
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.get_current_version",
        lambda: "0.1.5.dev646",
    )
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.fetch_latest_version",
        lambda index_url=None, **kwargs: "0.1.5",
    )
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.compare_versions",
        lambda current, latest: True,  # 0.1.5 > 0.1.5.dev646 → needs_update=True
    )
    # is_prerelease returns True ONLY for "0.1.5.dev646" (the prerelease)
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.is_prerelease",
        lambda v: v == "0.1.5.dev646",
    )
    monkeypatch.setattr(
        "teddy_executor.__main__._ensure_project_initialized",
        lambda container: None,
    )

    result = runner.invoke(app, ["update"])

    # Must show the force-install command (not upgrade)
    assert "uv tool install teddy-cli --force" in result.stdout, (
        f"Expected force-install command, got: {result.stdout!r}"
    )
    # Must NOT show the plain upgrade command
    assert "uv tool upgrade teddy-cli" not in result.stdout, (
        f"Should not show upgrade command, got: {result.stdout!r}"
    )
    # Must mention the new version
    assert "new version" in result.stdout.lower(), (
        f"Expected 'new version' in output, got: {result.stdout!r}"
    )
    assert "0.1.5" in result.stdout, (
        f"Expected version 0.1.5 in output, got: {result.stdout!r}"
    )
    assert result.exit_code == 0
