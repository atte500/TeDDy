"""Acceptance: bare ``teddy init`` auto-creates ``docs/templates/``.

Tracer bullet for the templates auto-initialization wiring. It drives the
outermost CLI boundary (``teddy init`` with no subcommand) and asserts the
final success state: the bundled Markdown templates are scaffolded into
``docs/templates/`` on first initialization.
"""

from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter

# The acceptance layer must not import core internals, so the expected
# template names are declared locally rather than imported from InitService.
EXPECTED_TEMPLATES = [
    "specification-document.md",
    "task-brief.md",
    "case-file.md",
    "vertical-slice.md",
    "milestone.md",
    "component-design.md",
    "ARCHITECTURE.md",
    "PROJECT.md",
    "makefile.md",
    "ci.md",
    "pre-commit.md",
]


def test_bare_teddy_init_scaffolds_docs_templates(tmp_path, monkeypatch):
    """``teddy init`` (no subcommand) creates ``docs/templates/`` with all bundled templates."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_config().with_real_filesystem().with_real_init_service()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # When
    result = adapter.run_command(["init"])

    # Then
    assert result.exit_code == 0, result.stdout

    templates_dir = tmp_path / "docs" / "templates"
    assert templates_dir.is_dir(), "docs/templates/ should be created on bare init"

    for name in EXPECTED_TEMPLATES:
        assert (templates_dir / name).is_file(), f"{name} should be scaffolded"
