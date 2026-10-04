"""Regression test: ``TEDDY_DIFF_TOOL`` must expand a leading ``~``.

Defect: ``ConsoleToolingHelper.get_diff_viewer_command`` resolved the
``TEDDY_DIFF_TOOL`` env-var override via ``shlex.split`` + ``which(parts[0])``
with no ``os.path.expanduser``. A diff tool referenced as ``~/bin/mydiff`` was
therefore looked up literally and rejected, even though the expanded path
exists and is executable -- the same class as the editor tilde gap fixed for
``_resolve_editor_cmd``. The branch now single-sources that resolver.

These tests assert the observable behaviour: a tilde-path override resolves to
its expanded absolute command, and any trailing arguments are preserved.
"""

import os

from tests.harness.setup.mocking import POSIXPathMock
from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment


def _helper_with_diff_tool(value: str, resolved: str) -> ConsoleToolingHelper:
    """Build a helper whose only resolvable command is ``resolved``."""
    mock_env = POSIXPathMock(spec=ISystemEnvironment)
    mock_config = POSIXPathMock(spec=IConfigService)
    helper = ConsoleToolingHelper(mock_env, mock_config)
    mock_env.get_env.side_effect = lambda key: (
        value if key == "TEDDY_DIFF_TOOL" else None
    )
    # POSIXPathMock normalizes the `which()` argument's backslashes to forward
    # slashes before the side_effect runs, so compare against the normalized
    # form (the raw Windows baseline keeps a `\` in the home component).
    normalized = resolved.replace("\\", "/")
    mock_env.which.side_effect = lambda name: resolved if name == normalized else None
    mock_config.get_setting.return_value = None  # no editor / diff_flags override
    return helper


def test_teddy_diff_tool_tilde_path_is_expanded():
    """A ``~/...`` diff tool resolves to its expanded absolute path."""
    # Arrange - only the EXPANDED path is resolvable.
    expanded = os.path.expanduser("~/bin/mydiff")
    helper = _helper_with_diff_tool("~/bin/mydiff", expanded)

    # Act
    result = helper.get_diff_viewer_command()

    # Assert - the tilde was expanded before the PATH lookup.
    assert result == [expanded]


def test_teddy_diff_tool_tilde_path_preserves_arguments():
    """A ``~/...`` diff tool with arguments keeps them after expansion."""
    # Arrange
    expanded = os.path.expanduser("~/bin/mydiff")
    helper = _helper_with_diff_tool("~/bin/mydiff --wait", expanded)

    # Act
    result = helper.get_diff_viewer_command()

    # Assert
    assert result == [expanded, "--wait"]
