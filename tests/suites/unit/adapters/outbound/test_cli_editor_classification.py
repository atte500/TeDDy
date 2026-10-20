"""Tests for the ask-loop editor classification delegation.

The ask loop no longer owns an editor classification table or predicate. It
delegates to the shared helper in `core/utils/editor_names.py`, so the TUI
reviewer and the console ask loop classify launcher-wrapped editors identically.
Wrapper classification itself is covered by the shared-helper unit tests and by
the ask-loop wiring flow.
"""

from __future__ import annotations

from teddy_executor.adapters.outbound import console_interactor_ask_loop
from teddy_executor.adapters.outbound.console_interactor_ask_loop import (
    ConsoleAskLoop,
)


def test_ask_loop_has_no_duplicated_editor_set() -> None:
    """A local copy would drift from the shared source of truth."""
    assert not hasattr(console_interactor_ask_loop, "_CLI_EDITORS")


def test_ask_loop_has_no_private_classifier() -> None:
    """Classification must go through the shared helper so every lookup matches."""
    assert not hasattr(ConsoleAskLoop, "_is_cli_editor")
