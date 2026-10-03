"""Regression tests: editor value persistence and resolution.

Defect 1 -- ``_prompt_for_editor_selection`` persisted the resolved ABSOLUTE
path (``available[i][1]``, e.g. ``/usr/bin/nvim``) instead of the selected
editor's basename (``available[i][0]``, e.g. ``nvim``). The README documents
the basename convention (``editor: "nvim"``), and an absolute path is
machine-specific (the Homebrew prefix differs between Intel and Apple Silicon),
so it does not travel with a copied config.

Defect 2 -- ``ConsoleToolingHelper._resolve_editor_cmd`` did not expand ``~``,
so a personal binary referenced as ``~/bin/myeditor`` was rejected even though
an absolute path to the same off-PATH executable is accepted.

These tests assert the observable behaviour the user expects: a numbered
selection persists the basename, and a tilde path resolves to its expanded
location.
"""

import os

from tests.harness.setup.mocking import POSIXPathMock
from teddy_executor.adapters.inbound.session_cli_handlers import (
    _prompt_for_editor_selection,
)
from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment


def _patch_prompt(monkeypatch, values):
    """Feed the given strings to successive ``typer.prompt`` calls."""
    iterator = iter(values)
    monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: next(iterator))


def test_editor_selection_persists_basename_not_resolved_path(monkeypatch):
    """A valid number persists the basename, not the resolved absolute path."""
    # Arrange
    mock_config = POSIXPathMock(spec=IConfigService)
    mock_env = POSIXPathMock(spec=ISystemEnvironment)
    helper = ConsoleToolingHelper(mock_env, mock_config)
    available = [("nvim", "/usr/bin/nvim"), ("vim", "/usr/bin/vim")]
    _patch_prompt(monkeypatch, ["1"])

    # Act
    _prompt_for_editor_selection(mock_config, helper, available)

    # Assert - the portable basename is stored, not the machine-specific path.
    mock_config.set_setting.assert_called_once_with("editor", "nvim")


def test_resolve_editor_cmd_expands_tilde_path():
    """A ``~/...`` editor command resolves to its expanded absolute path."""
    # Arrange - only the EXPANDED path resolves on PATH.
    mock_config = POSIXPathMock(spec=IConfigService)
    mock_env = POSIXPathMock(spec=ISystemEnvironment)
    helper = ConsoleToolingHelper(mock_env, mock_config)
    expanded = os.path.expanduser("~/bin/myeditor")
    mock_env.which.side_effect = lambda name: expanded if name == expanded else None

    # Act
    result = helper._resolve_editor_cmd("~/bin/myeditor")

    # Assert - the tilde was expanded before the PATH lookup.
    assert result == [expanded]
