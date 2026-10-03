"""Unit tests: ActionDispatcher maps the ShellOutput ``interrupted`` marker to
ActionStatus.INTERRUPTED (Bug 58 Option B).

When the shell adapter terminates an in-flight command because the user
interrupted the turn it returns a ShellOutput carrying ``interrupted: True``.
The dispatcher must surface that as INTERRUPTED (highest precedence for the
action), independent of the (negative) return code the kill produced.
"""

from typing import Any, Optional

from teddy_executor.core.domain.models import ActionData, ActionStatus
from teddy_executor.core.services.action_dispatcher import ActionDispatcher


class _StubAction:
    """Hand-rolled action double returning a canned result (not a mock)."""

    def __init__(self, result: Any) -> None:
        self._result = result

    def execute(self, **_kwargs: Any) -> Any:
        return self._result


class _StubFactory:
    """Hand-rolled factory double returning a fixed action."""

    def __init__(self, action: _StubAction) -> None:
        self._action = action

    def create_action(self, service_type: str, params: Optional[dict] = None) -> Any:
        _ = service_type, params
        return self._action


def _dispatch(result: Any):
    dispatcher = ActionDispatcher(action_factory=_StubFactory(_StubAction(result)))
    action = ActionData(type="EXECUTE", params={"command": "sleep 30"})
    return dispatcher.dispatch_and_execute(action)


def test_interrupted_shell_output_maps_to_interrupted_status():
    result = {
        "stdout": "partial",
        "stderr": "",
        "return_code": -9,
        "interrupted": True,
    }

    log = _dispatch(result)

    assert log.status == ActionStatus.INTERRUPTED


def test_non_interrupted_nonzero_return_code_still_maps_to_failure():
    result = {"stdout": "", "stderr": "boom", "return_code": 1}

    log = _dispatch(result)

    assert log.status == ActionStatus.FAILURE


def test_zero_return_code_without_marker_maps_to_success():
    result = {"stdout": "ok", "stderr": "", "return_code": 0}

    log = _dispatch(result)

    assert log.status == ActionStatus.SUCCESS
