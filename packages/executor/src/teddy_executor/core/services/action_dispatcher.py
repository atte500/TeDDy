import json
from typing import Protocol

from teddy_executor.core.domain.models import ActionData, V2_ActionLog


# --- Protocols for Dependencies ---


class IAction(Protocol):
    """Defines the interface for any action handler."""

    def execute(self, **kwargs) -> dict: ...


class IActionFactory(Protocol):
    """Defines the interface for the factory that creates actions."""

    def create_action(self, action_type: str) -> IAction: ...


# --- Service Implementation ---


class ActionDispatcher:
    """
    A service that dispatches a single action to its handler and logs the result.
    """

    def __init__(self, action_factory: IActionFactory):
        self._action_factory = action_factory

    def dispatch_and_execute(self, action_data: ActionData) -> V2_ActionLog:
        """
        Takes an ActionData object, finds the corresponding action handler
        via the factory, executes it, and returns the result as an ActionLog.
        """
        log_data: dict = {
            "action_type": action_data.type,
            "params": action_data.params,
        }

        try:
            action_handler = self._action_factory.create_action(action_data.type)
            execution_result = action_handler.execute(**action_data.params)
            log_data["status"] = "SUCCESS"
            log_data["details"] = json.dumps(execution_result)
        except Exception as e:
            log_data["status"] = "FAILURE"
            log_data["details"] = str(e)

        return V2_ActionLog(**log_data)
