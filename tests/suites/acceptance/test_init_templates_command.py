"""Acceptance: ``teddy init templates`` regenerates ``docs/templates/``.

Tracer bullet for the ``teddy init templates`` subcommand. It drives the
outermost CLI boundary and asserts the command exists, scaffolds the bundled
Markdown templates into ``docs/templates/``, and forces overwrite
(regeneration) rather than the non-destructive auto-init path used by bare
``teddy init`` / ``teddy start`` / ``teddy resume``.
"""

from pathlib import Path

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


def test_init_templates_command_scaffolds_and_overwrites(tmp_path, monkeypatch):
    """``teddy init templates`` populates ``docs/templates/`` and overwrites existing files."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_config().with_real_filesystem().with_real_init_service()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # Pre-seed a customized template. This proves the subcommand passes
    # overwrite=True: the bare auto-init path is non-destructive and would
    # leave a pre-existing file untouched.
    templates_dir: Path = tmp_path / "docs" / "templates"
    templates_dir.mkdir(parents=True)
    customized = templates_dir / "specification-document.md"
    customized.write_text("SENTINEL: user-customized", encoding="utf-8")

    # When
    result = adapter.run_command(["init", "templates"])

    # Then
    assert result.exit_code == 0, result.stdout

    for name in EXPECTED_TEMPLATES:
        assert (templates_dir / name).is_file(), f"{name} should be scaffolded"

    assert customized.read_text(encoding="utf-8") != "SENTINEL: user-customized", (
        "teddy init templates must overwrite existing templates (overwrite=True)"
    )