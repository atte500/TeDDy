"""Regression: the ShellAdapter in-flight interrupt test must not fail in SETUP on Windows.

The POSIX-only ``os.killpg`` symbol is absent on Windows, so an unguarded
``monkeypatch.setattr(os, "killpg", ...)`` raises AttributeError during test
SETUP. This test emulates the single Windows condition and asserts the interrupt
test guards its POSIX-only patch (skipping instead of erroring) so the Windows
CI leg stays green.
"""

import importlib.util
import os
import sys
from pathlib import Path

import pytest

_INTERRUPT_TEST_PATH = Path(__file__).with_name("test_shell_adapter_interrupt.py")


def _load_interrupt_test_module():
    """Import the sibling interrupt test module by file path (no package needed)."""
    spec = importlib.util.spec_from_file_location(
        "_shell_adapter_interrupt_under_emulation", _INTERRUPT_TEST_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_interrupt_test_skips_when_os_killpg_is_absent(monkeypatch):
    # Emulate the single Windows condition that triggers the CI failure:
    # os.killpg does not exist on Windows.
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delattr(os, "killpg", raising=False)

    module = _load_interrupt_test_module()

    # Guarded: the test must SKIP (raise Skipped), not AttributeError.
    with pytest.raises(pytest.skip.Exception):
        module.test_await_process_terminates_group_and_reports_interrupt(monkeypatch)
