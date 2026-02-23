import logging
from dataclasses import is_dataclass, asdict
from typing import Protocol, Any, Optional

from teddy_executor.core.domain.models import (
    ActionData,
    ActionLog,
    ActionStatus,
    CommandResult,
)


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

    def dispatch_and_execute(self, action_data: ActionData) -> ActionLog:
        """
        Takes an ActionData object, finds the corresponding action handler
        via the factory, executes it, and returns the result as an ActionLog.
        """
        logger.info(f"Executing: {action_data.type.upper()}")

        # Make a copy of params for logging and defensively add the description
        # to it if it exists. This makes the dispatcher robust against parser
        # inconsistencies where `description` is a separate attribute.
        log_params = action_data.params.copy()
        if action_data.description and "Description" not in log_params:
            log_params["Description"] = action_data.description

        log_data: dict = {
            "action_type": action_data.type,
            "params": log_params,
        }

        try:
            params_to_translate = log_data["params"]
            if not isinstance(params_to_translate, dict):
                # Handle legacy case where a single string param is provided for 'execute'
                if action_data.type == "execute":
                    params_to_translate = {"command": params_to_translate}
                    # Also update the params that will be logged
                    log_data["params"] = params_to_translate
                else:
                    # For other actions, a non-dict param is an error, as the
                    # intended keyword is ambiguous.
                    raise TypeError(
                        f"Action type '{action_data.type}' requires dictionary parameters, "
                        f"but received type '{type(params_to_translate).__name__}'."
                    )

            # --- Parameter Translation for Backwards Compatibility ---
            param_map = {
                "create_file": {"file_path": "path"},
                "edit": {"file_path": "path"},
                "read": {"source": "path", "resource": "path"},
            }

            mapping = param_map.get(action_data.type.lower(), {})
            translated_params = params_to_translate.copy()
            for old_key, new_key in mapping.items():
                if old_key in translated_params:
                    translated_params[new_key] = translated_params.pop(old_key)

            # The translated params (which include the Description) are now the
            # source of truth for logging.
            log_data["params"] = translated_params

            # Create a final copy of params for execution, and remove metadata fields
            # that are not intended for the action handlers.
            execution_only_params = translated_params.copy()
            execution_only_params.pop("expected_outcome", None)
            execution_only_params.pop("Description", None)

            # --- End of Translation ---

            action_handler = self._action_factory.create_action(
                action_data.type, execution_only_params
            )
            execution_result = action_handler.execute(**execution_only_params)

            # Convert dataclass to dict for serialization
            if is_dataclass(execution_result):
                result_to_serialize = asdict(execution_result)  # type: ignore[arg-type]
            else:
                result_to_serialize = execution_result

            # --- Normalize successful results for consistent reporting ---
            if isinstance(result_to_serialize, str):
                normalized_type = action_data.type.lower()
                if normalized_type == "read":
                    result_to_serialize = {"content": result_to_serialize}
                elif normalized_type == "chat_with_user":
                    result_to_serialize = {"response": result_to_serialize}

            # Determine status based on result type
            if isinstance(execution_result, CommandResult):
                if execution_result.return_code == 0:
                    log_data["status"] = ActionStatus.SUCCESS
                    logger.info(f"Success: {action_data.type.upper()}")
                else:
                    log_data["status"] = ActionStatus.FAILURE
                    logger.info(f"Failure: {action_data.type.upper()}")
            else:
                log_data["status"] = ActionStatus.SUCCESS
                logger.info(f"Success: {action_data.type.upper()}")

            log_data["details"] = result_to_serialize
        except Exception as e:
            log_data["status"] = ActionStatus.FAILURE
            log_data["details"] = str(e)
            logger.info(f"Failure: {action_data.type.upper()}")

        return ActionLog(**log_data)
