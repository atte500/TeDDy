"""Regression pins for the removal of the deprecated ``--console``/``--tui`` CLI mode.

These assertions are Poka-Yoke guards ensuring the console-mode flag surface
(``OPT_UI_MODE`` and the two ``apply_ui_mode_override`` helpers) cannot silently
re-appear once the Textual TUI has become the sole plan reviewer.
"""

import teddy_executor.__main__ as main_module
from teddy_executor.adapters.inbound import cli_helpers


def test_console_mode_flag_surface_is_removed():
    assert not hasattr(main_module, "OPT_UI_MODE")
    assert not hasattr(main_module, "_apply_ui_mode_override")
    assert not hasattr(cli_helpers, "apply_ui_mode_override")
