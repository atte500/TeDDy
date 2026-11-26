"""Harness unit tests: the user-interactor double's waiting operations.

The planning service brackets a model call with ``begin_waiting`` and a
``finally``-guarded ``end_waiting``, and the port's contract is "returns None".
The harness registers both as recording no-ops, so a harness-driven planning
flow stays deterministic instead of branching on a dynamic child mock, and the
bracketing order stays assertable from the double.
"""

from typing import Any

LABEL = "Waiting for pathfinder to respond..."


def test_interactor_waiting_defaults_are_recording_noops(env: Any) -> None:
    interactor = env.get_mock_user_interactor()

    # Assert: the registered defaults answer with the port's own value, so a
    # planning flow never observes a truthy dynamic mock as the answer.
    assert interactor.begin_waiting(LABEL) is None
    assert interactor.end_waiting() is None

    # Assert: both calls stay recorded, so the bracketing order is assertable.
    interactor.begin_waiting.assert_called_once_with(LABEL)
    interactor.end_waiting.assert_called_once_with()


def test_unbalanced_end_waiting_stays_a_silent_noop(env: Any) -> None:
    interactor = env.get_mock_user_interactor()

    # Act: a defensive ``finally`` may end a wait a failure already ended.
    assert interactor.end_waiting() is None
    assert interactor.end_waiting() is None

    # Assert: repeated ends neither raise nor answer dynamically.
    assert interactor.end_waiting.call_count == 2
