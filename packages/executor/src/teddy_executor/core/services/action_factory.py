from typing import Dict, Any

from teddy_executor.core.domain.models import (
    Action,
    ExecuteAction,
    CreateFileAction,
    ParsePlanAction,
    ReadAction,
    EditAction,
    ChatWithUserAction,
    ResearchAction,
)


class ActionFactory:
    _action_map = {
        "execute": ExecuteAction,
        "create_file": CreateFileAction,
        "parse_plan": ParsePlanAction,
        "read": ReadAction,
        "edit": EditAction,
        "chat_with_user": ChatWithUserAction,
        "research": ResearchAction,
    }

    @classmethod
    def create_action(cls, raw_action: Dict[str, Any]) -> Action:
        """
        Creates a specific Action subclass from a raw action dictionary.

        Args:
            raw_action: The dictionary parsed from the YAML plan.

        Returns:
            An instance of a concrete Action subclass.

        Raises:
            ValueError: If the action type is unknown.
            TypeError: If required parameters for an action are missing.
        """
        action_type = raw_action.get("action")
        if not isinstance(action_type, str):
            raise ValueError("Action type missing or not a string in the plan.")

        # All keys in the raw_action dict apart from 'action' are considered params.
        params = {k: v for k, v in raw_action.items() if k != "action"}

        action_class = cls._action_map.get(action_type)
        if not action_class:
            raise ValueError(f"Unknown action type: '{action_type}'")

        # Map external contract names (from YAML) to internal domain model parameter names.
        # This is a key decoupling point between the public contract and the core domain.
        if action_type in ["create_file", "edit"]:
            if "path" in params:
                params["file_path"] = params.pop("path")

        # Special handling for 'research' action to split queries string
        if action_type == "research" and isinstance(params.get("queries"), str):
            queries_str = params["queries"]
            params["queries"] = [
                q.strip() for q in queries_str.splitlines() if q.strip()
            ]

        # Handle legacy execute action where the value is just a command string
        if action_type == "execute" and "command" not in params and len(params) == 1:
            # This is brittle, assumes the single value is the command
            # A better approach would be to formalize the plan structure
            command_key = list(params.keys())[0]
            if command_key != "action":
                params["command"] = params.pop(command_key)

        return action_class(**params)
