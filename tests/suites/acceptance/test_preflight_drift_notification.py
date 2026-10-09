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
