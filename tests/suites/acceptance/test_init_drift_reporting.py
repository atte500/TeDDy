"""Acceptance: bare ``teddy init`` flags prompt and template drift.

Wiring (slice 00-39): after its non-destructive copy and summary echo, bare
``teddy init`` must print the SAME drift advice as ``teddy start`` -- a yellow
count-aware line naming the actionable command (``teddy init prompts`` /
``teddy init templates``) and the shared disable-footer naming the fired checks.
The destructive subcommands stay unchanged.
"""

from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter


def test_init_advises_drifted_prompt_and_missing_templates(tmp_path, monkeypatch):
    """Scenario: a stale prompt and an absent docs/templates/ yield the advice."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_config().with_real_filesystem().with_real_init_service()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # Arrange: a workspace whose `.teddy/prompts/` holds a stale `.xml` prompt
    # and no `.md` prompts. Bare `teddy init` does NOT scaffold docs/templates/
    # (the reversed contract), so every bundled template also reports as MISSING.
    prompts_dir = tmp_path / ".teddy" / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "pathfinder.xml").write_text(
        "<user-edited-prompt/>", encoding="utf-8"
    )
    (tmp_path / "README.md").write_text("# Demo", encoding="utf-8")

    # Act
    result = adapter.run_command(["init"])

    # Assert: the drift block advises the actionable commands.
    assert result.exit_code == 0, result.stdout
    output = result.stdout + result.stderr
    assert "teddy init prompts" in output, (
        "A drifted prompt must trigger the 'teddy init prompts' advice; "
        f"got: {output!r}"
    )
    assert "teddy init templates" in output, (
        "Missing templates must trigger the 'teddy init templates' advice; "
        f"got: {output!r}"
    )

    # Assert: the single shared disable-footer names both fired checks in the
    # canonical order (prompts, then templates).
    assert (
        "You can disable these checks in .teddy/config.yaml: "
        "checks.prompts, checks.templates." in output
    ), f"The shared disable-footer must name both fired checks; got: {output!r}"
