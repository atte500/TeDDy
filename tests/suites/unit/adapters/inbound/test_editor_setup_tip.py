"""Tests: the editor-setup hint is rendered in BOTH setup branches.

The hint gives a user whose editor is missing a way forward -- add it to PATH,
or enter an absolute path (``which()`` resolves a direct/absolute path even
when the binary is off-PATH). It is emitted on stderr, so the assertions read
``capsys``.
"""

from tests.harness.setup.mocking import POSIXPathMock
from teddy_executor.adapters.inbound.session_cli_handlers import (
    _prompt_for_custom_editor,
    _prompt_for_editor_selection,
)
from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment

EXPECTED_TIP = (
    "Tip: Don't see your editor? Make sure it's available in your PATH, "
    "or enter its absolute path below."
)


def _patch_prompt(monkeypatch, values):
    """Feed the given strings to successive ``typer.prompt`` calls."""
    iterator = iter(values)
    monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: next(iterator))


def _helper():
    return ConsoleToolingHelper(
        POSIXPathMock(spec=ISystemEnvironment),
        POSIXPathMock(spec=IConfigService),
    )


def test_selection_branch_prints_the_hint(monkeypatch, capsys):
    """The editors-found branch shows the hint before the selection prompt."""
    mock_config = POSIXPathMock(spec=IConfigService)
    available = [("nvim", "/usr/bin/nvim"), ("vim", "/usr/bin/vim")]
    _patch_prompt(monkeypatch, [""])  # empty -> disable, ends the loop

    _prompt_for_editor_selection(mock_config, _helper(), available)

    assert EXPECTED_TIP in capsys.readouterr().err


def test_custom_branch_prints_the_hint(monkeypatch, capsys):
    """The nothing-found branch shows the hint before the custom prompt."""
    mock_config = POSIXPathMock(spec=IConfigService)
    _patch_prompt(monkeypatch, [""])  # empty -> disable, ends the loop

    _prompt_for_custom_editor(mock_config, _helper())

    assert EXPECTED_TIP in capsys.readouterr().err
