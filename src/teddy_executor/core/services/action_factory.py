from typing import Any, Dict, Type
import punq
from teddy_executor.core.ports.outbound import (
    IShellExecutor,
    IFileSystemManager,
    IUserInteractor,
    IWebSearcher,
)
from teddy_executor.core.services.action_dispatcher import IAction, IActionFactory


class InvokeAction:
    def execute(self, **kwargs: Any) -> str:
        agent = kwargs.get("agent", "Unknown")
        return f"INVOKE action recognized for agent: {agent}"


class ActionFactory(IActionFactory):
    """
    A protocol-compliant factory that uses the DI container to resolve action handlers.
    """

    # Maps uppercase verbs from Markdown plans to the internal, descriptive keys.
    _MARKDOWN_ACTION_MAP = {
        "CREATE": "create_file",
        "EDIT": "edit",
        "READ": "read",
        "EXECUTE": "execute",
        "INVOKE": "invoke",
        "CHAT_WITH_USER": "chat_with_user",
        "RESEARCH": "research",
        "PRUNE": "prune",
    }

    def __init__(self, container: punq.Container):
        self._container = container
        self._action_map: Dict[str, Type] = {
            "execute": IShellExecutor,
            "create_file": IFileSystemManager,
            "edit": IFileSystemManager,
            "read": IFileSystemManager,
            "chat_with_user": IUserInteractor,
            "research": IWebSearcher,
            "invoke": InvokeAction,
        }

    def _normalize_action_type(self, action_type: str) -> str:
        """
        Normalizes action types from different plan formats to the internal key format.
        """
        # First, check the explicit mapping for Markdown verbs.
        if action_type in self._MARKDOWN_ACTION_MAP:
            return self._MARKDOWN_ACTION_MAP[action_type]
        # Fallback to lowercasing for YAML/other formats.
        return action_type.lower()

    def create_action(self, action_type: str) -> IAction:
        """
        Looks up the adapter protocol for the given action type and asks the
        container to resolve an instance of it. It then binds the correct
        adapter method to the `execute` method required by the IAction protocol.
        """
        action_type_key = self._normalize_action_type(action_type)
        if action_type_key not in self._action_map:
            raise ValueError(f"Unknown action type: '{action_type}'")

        adapter_protocol = self._action_map[action_type_key]
        if adapter_protocol == InvokeAction:
            return InvokeAction()
        action_handler = self._container.resolve(adapter_protocol)

        method_map = {
            "create_file": "create_file",
            "edit": "edit_file",
            "read": "read_file",
            "chat_with_user": "ask_question",
            "research": "search",
        }

        if action_type_key in method_map:
            method_name = method_map[action_type_key]
            setattr(action_handler, "execute", getattr(action_handler, method_name))
        elif not hasattr(action_handler, "execute"):
            raise NotImplementedError(
                f"Adapter for {action_type} does not have a default 'execute' method."
            )

        return action_handler
