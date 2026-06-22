"""Acceptance tests for the --version flag and version subcommand."""

from typer.testing import CliRunner


def test_version_flag_displays_installed_version(monkeypatch):
    """`teddy --version` should display 'TeDDy vX.Y.Z'."""
    from teddy_executor.__main__ import app

    # Mock the version to a known value for deterministic assertions
    monkeypatch.setattr(
        "importlib.metadata.version",
        lambda pkg_name: "0.1.0" if pkg_name == "teddy-cli" else "0.0.0",
    )

    runner = CliRunner()
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0, (
        f"Expected exit code 0 for --version flag, "
        f"got {result.exit_code}. Output: {result.stdout!r}"
    )
    assert "TeDDy v0.1.0" in result.stdout, (
        f"Expected stdout to contain 'TeDDy v0.1.0', got: {result.stdout!r}"
    )


def test_version_command_displays_installed_version(monkeypatch):
    """`teddy version` should display 'TeDDy vX.Y.Z'."""
    from teddy_executor.__main__ import app

    monkeypatch.setattr(
        "importlib.metadata.version",
        lambda pkg_name: "0.1.0" if pkg_name == "teddy-cli" else "0.0.0",
    )

    runner = CliRunner()
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0, (
        f"Expected exit code 0 for version command, "
        f"got {result.exit_code}. Output: {result.stdout!r}"
    )
    assert "TeDDy v0.1.0" in result.stdout, (
        f"Expected stdout to contain 'TeDDy v0.1.0', got: {result.stdout!r}"
    )
