from dataclasses import is_dataclass, asdict
from typing import Protocol, Any

from teddy_executor.core.domain.models import ActionData, ActionLog, CommandResult


# --- Protocols for Dependencies ---


class IAction(Protocol):
    """Defines the interface for any action handler."""

    def execute(self, **kwargs) -> Any: ...


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

    def dispatch_and_execute(self, action_data: ActionData) -> ActionLog:
        """
        Takes an ActionData object, finds the corresponding action handler
        via the factory, executes it, and returns the result as an ActionLog.
        """
        log_data: dict = {
            "action_type": action_data.type,
            "params": action_data.params,
        }

        try:
            execution_params = action_data.params
            if not isinstance(execution_params, dict):
                # Handle legacy case where a single string param is provided for 'execute'
                if action_data.type == "execute":
                    execution_params = {"command": execution_params}
                else:
                    # For other actions, a non-dict param is an error, as the
                    # intended keyword is ambiguous.
                    raise TypeError(
                        f"Action type '{action_data.type}' requires dictionary parameters, "
                        f"but received type '{type(execution_params).__name__}'."
                    )

            # --- Parameter Translation for Backwards Compatibility ---
            param_map = {
                "create_file": {"file_path": "path"},
                "edit": {"file_path": "path"},
                "read": {"source": "path", "resource": "path"},
            }

            mapping = param_map.get(action_data.type.lower(), {})
            translated_params = execution_params.copy()
            for old_key, new_key in mapping.items():
                if old_key in translated_params:
                    translated_params[new_key] = translated_params.pop(old_key)

            # Remove metadata parameters that are not used by adapters
            translated_params.pop("expected_outcome", None)

            # --- End of Translation ---

            action_handler = self._action_factory.create_action(action_data.type)
            execution_result = action_handler.execute(**translated_params)

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
                    log_data["status"] = "SUCCESS"
                else:
                    log_data["status"] = "FAILURE"
            else:
                log_data["status"] = "SUCCESS"

            log_data["details"] = result_to_serialize
        except Exception as e:
            log_data["status"] = "FAILURE"
            log_data["details"] = str(e)

        return ActionLog(**log_data)
