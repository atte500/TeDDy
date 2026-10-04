"""Unit tests for the ``isatty`` contract on ``ISystemEnvironment``.

The one-time editor-setup gate (Slice 00-26) keys on a terminal-availability
signal, so the ``ISystemEnvironment`` port must expose ``isatty()`` and the
concrete ``SystemEnvironmentAdapter`` must delegate it to ``sys.stdin.isatty()``.
A Protocol method declared with ``...`` returns ``None`` when not overridden, so
an un-overridden member would silently disable the gate.
"""

import sys

import pytest

from teddy_executor.adapters.outbound.system_environment_adapter import (
    SystemEnvironmentAdapter,
)
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment


def test_isystem_environment_protocol_declares_isatty():
    """The port must declare ``isatty()`` so adapters can satisfy the seam."""
    assert hasattr(ISystemEnvironment, "isatty"), (
        "ISystemEnvironment must declare isatty()"
    )


@pytest.mark.parametrize("tty", [True, False])
def test_system_environment_adapter_delegates_isatty(monkeypatch, tty):
    """The concrete adapter forwards ``sys.stdin.isatty()`` (never a stub ``None``)."""
    monkeypatch.setattr(sys.stdin, "isatty", lambda: tty)

    adapter = SystemEnvironmentAdapter()

    assert adapter.isatty() is tty
