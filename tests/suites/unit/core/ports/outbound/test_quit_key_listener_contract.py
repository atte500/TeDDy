"""Contract tests: the IQuitKeyListener outbound port (Bug 56 bare-`q`).

The listener is a greenfield outbound port abstracting an environment-agnostic
single-key quit trigger for terminals that never deliver a Ctrl+C byte. These
tests pin the port's structural contract only (interface shape); the concrete
reader's behavior (idempotent lifecycle, off-TTY no-op, byte detection) is
pinned by the downstream reader suites once the implementation exists.

Mirrors the established outbound-port contract convention
(``test_time_service_contract.py``).
"""

import inspect
from typing import Protocol, runtime_checkable

from teddy_executor.core.ports.outbound.quit_key_listener import (
    IQuitKeyListener,
    QuitCallback,
)


def test_quit_key_listener_is_a_runtime_checkable_protocol():
    """The port is a runtime-checkable typing Protocol."""
    assert issubclass(IQuitKeyListener, Protocol)
    assert runtime_checkable(IQuitKeyListener)


def test_quit_key_listener_exposes_the_start_stop_lifecycle():
    """The abstraction exposes exactly the start()/stop() lifecycle."""
    assert hasattr(IQuitKeyListener, "start")
    assert hasattr(IQuitKeyListener, "stop")


def test_quit_key_listener_lifecycle_methods_are_parameterless():
    """start()/stop() take no arguments beyond self."""
    for name in ("start", "stop"):
        signature = inspect.signature(getattr(IQuitKeyListener, name))
        assert list(signature.parameters) == ["self"], (
            f"{name}() must be parameterless, got {list(signature.parameters)}"
        )


class _ConformingListener:
    """Minimal hand-rolled conforming double (not a mock)."""

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


def test_port_is_satisfied_by_a_conforming_double():
    """A class implementing start()/stop() satisfies the port (isinstance)."""
    assert isinstance(_ConformingListener(), IQuitKeyListener)


def test_quit_callback_alias_describes_the_on_quit_hook():
    """The module exports the `on_quit` hook type for implementations."""

    def _noop() -> None:
        return None

    callback: QuitCallback = _noop
    assert callable(callback)
