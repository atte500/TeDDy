"""Contract tests: the IUserInteractor waiting operations.

``begin_waiting`` / ``end_waiting`` are display-only activity notifications the
planning service brackets around a model call. Two properties keep the
extension additive: the operations carry no-op default bodies, so an adapter
written against the older contract stays instantiable, and those bodies are
silent, so an implementation that ignores them renders nothing.
"""

import inspect

import pytest

from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor


def test_port_declares_both_waiting_operations() -> None:
    # Assert: the planning service can bracket a model call through the port.
    assert callable(getattr(IUserInteractor, "begin_waiting", None))
    assert callable(getattr(IUserInteractor, "end_waiting", None))


def test_begin_waiting_takes_the_presentation_hint() -> None:
    # Assert: the wording crosses the boundary as one string, so the core owns
    # what is said and the adapter owns how it is drawn.
    parameters = list(inspect.signature(IUserInteractor.begin_waiting).parameters)

    assert parameters == ["self", "message"]


def test_end_waiting_takes_no_argument() -> None:
    parameters = list(inspect.signature(IUserInteractor.end_waiting).parameters)

    assert parameters == ["self"]


def test_waiting_operations_are_not_abstract() -> None:
    """A shipped adapter must stay instantiable without overriding them.

    An abstract addition to a shared seam breaks every existing implementation
    until each one implements it, which is exactly the breaking change the
    additive rule forbids.
    """
    assert "begin_waiting" not in IUserInteractor.__abstractmethods__
    assert "end_waiting" not in IUserInteractor.__abstractmethods__


def test_default_bodies_render_nothing(capsys) -> None:
    # Act: the base bodies touch no instance state, so they are exercised
    # directly; an adapter overrides them to draw.
    assert IUserInteractor.begin_waiting(None, "Waiting for pathfinder...") is None
    assert IUserInteractor.end_waiting(None) is None

    # Assert: silence — no animation control characters, no stray line.
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_default_bodies_tolerate_unbalanced_and_nested_calls(capsys) -> None:
    # Act: a defensive ``finally`` may end a region a failure already ended, and
    # a nested begin must not stack a second region.
    IUserInteractor.end_waiting(None)
    IUserInteractor.begin_waiting(None, "Waiting for pathfinder...")
    IUserInteractor.begin_waiting(None, "Waiting again...")
    IUserInteractor.end_waiting(None)
    IUserInteractor.end_waiting(None)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


@pytest.mark.parametrize("operation", ["begin_waiting", "end_waiting"])
def test_waiting_operations_are_display_only(operation: str) -> None:
    # Assert: neither operation asks the user anything, so neither reads stdin.
    source = inspect.getsource(getattr(IUserInteractor, operation))

    assert "input(" not in source
    assert "signal" not in source
