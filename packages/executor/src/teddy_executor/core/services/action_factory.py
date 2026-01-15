from typing import Dict, Type
import punq
from teddy_executor.core.ports.outbound import (
    IShellExecutor,
    IFileSystemManager,
    IUserInteractor,
    IWebSearcher,
)
from teddy_executor.core.services.action_dispatcher import IAction, IActionFactory


class ActionFactory(IActionFactory):
    """
    A protocol-compliant factory that uses the DI container to resolve action handlers.
    """

    def __init__(self, container: punq.Container):
        self._container = container
        self._action_map: Dict[str, Type] = {
            "execute": IShellExecutor,
            "create_file": IFileSystemManager,
            "edit": IFileSystemManager,
            "read": IFileSystemManager,
            "chat_with_user": IUserInteractor,
            "research": IWebSearcher,
        }

    def create_action(self, action_type: str) -> IAction:
        """
        Looks up the adapter protocol for the given action type and asks the
        container to resolve an instance of it. It then binds the correct
        adapter method to the `execute` method required by the IAction protocol.
        """
        action_type_key = action_type.lower()
        if action_type_key not in self._action_map:
            raise ValueError(f"Unknown action type: '{action_type}'")

        adapter_protocol = self._action_map[action_type_key]
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
