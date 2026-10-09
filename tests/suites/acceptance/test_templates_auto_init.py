"""Acceptance: bare ``teddy init`` does NOT create ``docs/templates/``.

Reversed contract (Item 1): ``docs/templates/`` is scaffolded ONLY by the
explicit ``teddy init templates`` subcommand. Bare ``teddy init`` -- and the
``teddy start`` / ``teddy resume`` paths that share
``InitService.ensure_initialized`` -- must leave ``docs/templates/`` untouched.
"""

from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter


def test_bare_teddy_init_does_not_scaffold_docs_templates(tmp_path, monkeypatch):
    """``teddy init`` (no subcommand) must NOT create ``docs/templates/``."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_config().with_real_filesystem().with_real_init_service()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # When
    result = adapter.run_command(["init"])

    # Then
    assert result.exit_code == 0, result.stdout

    templates_dir = tmp_path / "docs" / "templates"
    assert not templates_dir.exists(), (
        "docs/templates/ must NOT be created by bare `teddy init`; only the "
        "explicit `teddy init templates` subcommand may scaffold it"
    )
