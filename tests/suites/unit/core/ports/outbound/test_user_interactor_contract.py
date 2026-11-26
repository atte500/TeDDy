"""Contract tests: the IUserInteractor waiting operations.

``begin_waiting`` / ``end_waiting`` are display-only activity notifications the
planning service brackets around a model call. Two properties keep the
extension additive: the operations carry no-op default bodies, so an adapter
written against the older contract stays instantiable, and those bodies are
silent, so an implementation that ignores them renders nothing.

The silence cases drive the real default bodies through a hand-rolled
conforming adapter, because an unbound receiver would assert about a shape the
port never has.
"""

import inspect
from typing import Optional

import pytest

from teddy_executor.core.domain.models import ActionData, ChangeSet, Plan
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


class _SilentInteractor(IUserInteractor):
    """A conforming adapter that inherits the port's default waiting bodies.

    Every abstract operation answers trivially, so the two display-only
    notifications under test are the inherited defaults rather than overrides.
    """

    def prompt(self, text: str, default: str = "") -> str:
        return default

    def ask_question(
        self,
        prompt: str,
        resources: list[str] | None = None,
        agent_name: Optional[str] = None,
    ) -> str:
        return ""

    def display_message(self, message: str) -> None:
        return None

    def confirm_plan_review(self, plan: Plan) -> bool:
        return True

    def confirm_action(
        self,
        action: ActionData,
        action_prompt: str,
        change_set: Optional[ChangeSet] = None,
    ) -> tuple[bool, str]:
        return True, ""

    def notify_skipped_action(self, action: ActionData, reason: str) -> None:
        return None

    def confirm_manual_handoff(
        self,
        action_type: str,
        target_agent: str | None,
        resources: list[str],
        message: str,
    ) -> tuple[bool, str]:
        return True, ""

    def notify_warning(self, message: str) -> None:
        return None


def _assert_no_output(capsys: pytest.CaptureFixture[str]) -> None:
    """Assert the wait rendered no bytes at all."""
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_waiting_operations_are_not_abstract() -> None:
    """A shipped adapter must stay instantiable without overriding them.

    An abstract addition to a shared seam breaks every existing implementation
    until each one implements it, which is exactly the breaking change the
    additive rule forbids.
    """
    assert "begin_waiting" not in IUserInteractor.__abstractmethods__
    assert "end_waiting" not in IUserInteractor.__abstractmethods__


def test_default_bodies_render_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    interactor = _SilentInteractor()

    # Act: an adapter that ignores the notifications inherits these bodies.
    interactor.begin_waiting("Waiting for pathfinder...")
    interactor.end_waiting()

    # Assert: silence — no animation control characters, no stray line.
    _assert_no_output(capsys)


def test_default_bodies_tolerate_unbalanced_and_nested_calls(
    capsys: pytest.CaptureFixture[str],
) -> None:
    interactor = _SilentInteractor()

    # Act: a defensive ``finally`` may end a region a failure already ended, and
    # a nested begin must not stack a second region.
    interactor.end_waiting()
    interactor.begin_waiting("Waiting for pathfinder...")
    interactor.begin_waiting("Waiting again...")
    interactor.end_waiting()
    interactor.end_waiting()

    _assert_no_output(capsys)


@pytest.mark.parametrize("operation", ["begin_waiting", "end_waiting"])
def test_waiting_operations_are_display_only(operation: str) -> None:
    # Assert: neither operation asks the user anything, so neither reads stdin.
    source = inspect.getsource(getattr(IUserInteractor, operation))

    assert "input(" not in source
    assert "signal" not in source
