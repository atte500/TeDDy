"""Regression pin for the retirement of the hidden non-interactive CLI aliases.

Slice 00-26 folds in the user-approved debt fix: the redundant hidden aliases
``--yes`` / ``--no-interactive`` / ``--non-interactive`` are removed from
``start`` / ``resume`` / ``execute`` so that ``interactive`` means approval-only
and the documented headless path is ``-y`` (a concrete flag) or non-TTY stdin.
This adapter-surface test drives the real CLI in-process and asserts each retired
alias is now rejected as an unknown option.
"""

import pytest

from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.test_environment import TestEnvironment


@pytest.mark.parametrize("flag", ["--yes", "--no-interactive", "--non-interactive"])
def test_retired_hidden_flags_are_rejected_by_start(tmp_path, monkeypatch, flag):
    """The retired aliases must no longer be accepted by ``start``.

    An unknown-option usage error (Click exit code 2 + "No such option") proves
    the alias is gone; a zero exit or any other outcome means the alias is still
    registered.
    """
    TestEnvironment(monkeypatch, tmp_path).setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    result = adapter.run_start([flag, "-m", "x"])

    output = result.stdout + result.stderr
    assert result.exit_code != 0
    assert "No such option" in output
