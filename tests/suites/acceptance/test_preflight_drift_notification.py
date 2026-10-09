"""Acceptance: a drifted user prompt triggers the ``teddy init prompts`` advice.

Wiring Items 3/4/5 (session-behaviour): at the ``teddy start`` preflight the CLI
must compare the user's ``.teddy/prompts/`` and ``docs/templates/`` against the
bundled defaults and, when they have drifted, emit a yellow message naming the
actionable command (``teddy init prompts`` / ``teddy init templates``).
"""

from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter


def test_start_advises_init_prompts_when_a_prompt_has_drifted(tmp_path, monkeypatch):
    """Scenario (Edited prompt): a user-edited prompt yields the init-prompts advice."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_filesystem()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # Arrange: a workspace whose pathfinder prompt DIFFERS from the bundled default.
    # init's _init_prompts(overwrite=False) will not clobber it and will fill in the
    # remaining defaults, leaving exactly one EDITED prompt.
    prompts_dir = tmp_path / ".teddy" / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "pathfinder.xml").write_text(
        "<user-edited-prompt/>", encoding="utf-8"
    )
    (tmp_path / "README.md").write_text("# Demo", encoding="utf-8")

    # Act
    result = adapter.run_start(["-y", "-m", "hello"])

    # Assert: the preflight advises the actionable command for prompt drift.
    output = result.stdout + result.stderr
    assert "teddy init prompts" in output, (
        "A drifted prompt must trigger the 'teddy init prompts' preflight advice; "
        f"got: {output!r}"
    )


def test_start_advises_init_templates_when_a_template_is_missing(tmp_path, monkeypatch):
    """Scenario (Missing template): an incomplete docs/templates/ yields the advice."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_filesystem()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # Arrange: a workspace that has opted into docs/templates/ but is MISSING at
    # least one bundled default template. A single local file keeps the directory
    # present while the remaining defaults are absent, so the advice fires whether
    # the classifier is per-file or directory-guarded. Bare `teddy init` does NOT
    # scaffold docs/templates/ (the reversed contract), so the start preflight
    # leaves this directory exactly as arranged.
    templates_dir = tmp_path / "docs" / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    (templates_dir / "vertical-slice.md").write_text("# local slice", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo", encoding="utf-8")

    # Act
    result = adapter.run_start(["-y", "-m", "hello"])

    # Assert: the preflight advises the actionable command for template drift.
    output = result.stdout + result.stderr
    assert "teddy init templates" in output, (
        "A missing template must trigger the 'teddy init templates' preflight "
        f"advice; got: {output!r}"
    )
