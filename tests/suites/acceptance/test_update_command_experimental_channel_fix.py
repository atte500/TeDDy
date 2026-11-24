"""Regression test for Bug #20: experimental channel shows wrong upgrade command.

When current is a prerelease (PyPI pre-release channel) and latest is a strictly
newer stable, `teddy update` (without --experimental) shows:
    uv tool upgrade teddy-cli --prerelease disallow

`--prerelease disallow` keeps the bug #20 fix (a bare `uv tool upgrade` follows
the receipt's `prerelease = "allow"` to a newer dev release) while preserving the
recorded install source that a `--force` reinstall discards.
"""

import typer.testing

from teddy_executor.__main__ import app


runner = typer.testing.CliRunner()


def test_prerelease_current_with_newer_stable_upgrades_to_stable(monkeypatch):
    """Bug #20: Current prerelease (0.1.5.dev646) < latest stable (0.1.5).

    Expected: 'uv tool upgrade teddy-cli --prerelease disallow'. A bare upgrade
    would follow the receipt's `prerelease = "allow"` to a newer dev release.
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
    result = runner.invoke(app, ["update"])

    # Must show the pre-release-to-stable upgrade command
    assert "uv tool upgrade teddy-cli --prerelease disallow" in result.stdout, (
        f"Expected pre-release-to-stable upgrade, got: {result.stdout!r}"
    )
    # Must NOT force a reinstall, which discards the recorded install source
    assert "uv tool install teddy-cli --force" not in result.stdout, (
        f"Should not force a reinstall, got: {result.stdout!r}"
    )
    # Must mention the new version
    assert "new version" in result.stdout.lower(), (
        f"Expected 'new version' in output, got: {result.stdout!r}"
    )
    assert "0.1.5" in result.stdout, (
        f"Expected version 0.1.5 in output, got: {result.stdout!r}"
    )
    assert result.exit_code == 0
