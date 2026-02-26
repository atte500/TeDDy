import logging
from dataclasses import is_dataclass, asdict
from typing import Protocol, Any, Optional

from teddy_executor.core.domain.models import (
    ActionData,
    ActionLog,
    ActionStatus,
)
from teddy_executor.core.domain.models.shell_output import ShellOutput


# --- Protocols for Dependencies ---


class IAction(Protocol):
    """Defines the interface for any action handler."""

    def execute(self, **kwargs) -> Any: ...


class IActionFactory(Protocol):
    """Defines the interface for the factory that creates actions."""

    def create_action(
        self, action_type: str, params: Optional[dict] = None
    ) -> IAction: ...


logger = logging.getLogger(__name__)

# --- Service Implementation ---


class ActionDispatcher:
    """
    A service that dispatches a single action to its handler and logs the result.
    """

    def __init__(self, action_factory: IActionFactory):
        self._action_factory = action_factory

    def _prepare_execution_params(self, action_data: ActionData) -> dict[str, Any]:
        """Handles parameter validation, translation, and cleaning."""
        params = action_data.params.copy()
        if not isinstance(params, dict):
            if action_data.type == "execute":
                return {"command": params}
            raise TypeError(
                f"Action type '{action_data.type}' requires dictionary parameters, but received type '{type(params).__name__}'."
            )

        param_map = {
            "create_file": {"file_path": "path"},
            "edit": {"file_path": "path"},
            "read": {"source": "path", "resource": "path"},
        }
        mapping = param_map.get(action_data.type.lower(), {})
        for old_key, new_key in mapping.items():
            if old_key in params:
                params[new_key] = params.pop(old_key)

        params.pop("expected_outcome", None)
        params.pop("Description", None)
        return params

    def _execute_and_process_result(
        self, action_type: str, execution_params: dict[str, Any]
    ) -> tuple[Any, ActionStatus]:
        """Executes the action, normalizes the result, and determines status."""
        action_handler = self._action_factory.create_action(
            action_type, execution_params
        )
        result = action_handler.execute(**execution_params)

        if is_dataclass(result) and not isinstance(result, type):
            result = asdict(result)

        if isinstance(result, str):
            if action_type.lower() == "read":
                result = {"content": result}
            elif action_type.lower() == "chat_with_user":
                result = {"response": result}

        status = ActionStatus.SUCCESS
        if isinstance(result, dict) and "return_code" in result:
            shell_output: ShellOutput = result  # type: ignore
            if shell_output["return_code"] != 0:
                status = ActionStatus.FAILURE
        return result, status

    def dispatch_and_execute(self, action_data: ActionData) -> ActionLog:
        """
        Takes an ActionData object, finds the corresponding action handler
        via the factory, executes it, and returns the result as an ActionLog.
        """
        action_name = action_data.type.upper()
        log_desc = f" - {action_data.description}" if action_data.description else ""
        logger.info(f"{action_name}{log_desc}")

        log_params = action_data.params.copy()
        if action_data.description and "Description" not in log_params:
            log_params["Description"] = action_data.description

        log_data: dict = {
            "action_type": action_data.type,
            "params": log_params,
        }

        try:
            execution_params = self._prepare_execution_params(action_data)
            details, status = self._execute_and_process_result(
                action_data.type, execution_params
            )
            log_data["details"] = details
            log_data["status"] = status
            logger.info(status.value.upper())
        except Exception as e:
            log_data["status"] = ActionStatus.FAILURE
            log_data["details"] = str(e)
            logger.info("FAILURE")

        return ActionLog(**log_data)
