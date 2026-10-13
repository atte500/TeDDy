"""Regression: the `teddy start` preflight notification output.

Locks the user-facing preflight contract for the drift notification block:

  1. The drift advice line and its shared disable-footer read as ONE adjacent
     block; the blank separator sits ABOVE the block, not between them.
  2. The drift advice reads "To update them, run:" (not "To overwrite").
  3. The misleading "API key valid! Model: ... | Agent: ..." banner is not
     printed (no API-key validity check ever runs).

Assertions target the observable CLI output, not internal helper details.
"""

import re

from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.test_environment import TestEnvironment


_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def _plain(text: str) -> str:
    return _ANSI_ESCAPE.sub("", text)


def _seed_drifted_prompt_workspace(tmp_path) -> None:
    """A workspace whose pathfinder prompt differs from the bundled default."""
    prompts_dir = tmp_path / ".teddy" / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "pathfinder.xml").write_text(
        "<user-edited-prompt/>", encoding="utf-8"
    )
    (tmp_path / "README.md").write_text("# Demo", encoding="utf-8")


def test_start_preflight_groups_drift_advice_with_its_disable_footer(
    tmp_path, monkeypatch
):
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_filesystem()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    _seed_drifted_prompt_workspace(tmp_path)

    result = adapter.run_start(["-y", "-m", "hello"])

    stdout = _plain(result.stdout)
    combined = _plain(result.stdout + result.stderr)

    # Wording: the advice says "To update them", never "To overwrite".
    assert "To update them, run: teddy init prompts" in stdout, stdout
    assert "To overwrite" not in combined, combined

    # Grouping: a blank separator sits ABOVE the advice block...
    assert "\nℹ" in stdout, stdout
    # ...and the disable-footer directly follows the last advice line (no blank
    # line wedged between them).
    assert "\nYou can disable" in stdout, stdout
    assert "\n\nYou can disable" not in stdout, stdout


def test_start_preflight_omits_the_config_success_banner(tmp_path, monkeypatch):
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_filesystem()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    _seed_drifted_prompt_workspace(tmp_path)

    result = adapter.run_start(["-y", "-m", "hello"])

    combined = _plain(result.stdout + result.stderr)
    assert "API key valid" not in combined, (
        f"The misleading config-success banner must not be printed; got: {combined!r}"
    )
