from typing import Dict, Any

from teddy.core.domain.models import (
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

        params = raw_action.get("params", {})

        action_class = cls._action_map.get(action_type)
        if not action_class:
            raise ValueError(f"Unknown action type: '{action_type}'")

        return action_class(**params)
