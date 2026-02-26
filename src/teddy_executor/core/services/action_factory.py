from typing import Any, Dict, Type, Optional
import punq
from teddy_executor.core.ports.outbound import (
    IShellExecutor,
    IFileSystemManager,
    IUserInteractor,
    IWebScraper,
    IWebSearcher,
)
from teddy_executor.core.services.action_dispatcher import IAction, IActionFactory


class InvokeAction:
    def execute(self, **kwargs: Any) -> str:
        agent = kwargs.get("agent", "Unknown")
        return f"INVOKE action recognized for agent: {agent}"


class PruneAction:
    def execute(self, **kwargs: Any) -> str:
        resource = kwargs.get("resource", "Unknown")
        return f"PRUNE action recognized for resource: {resource}"


class ConcludeAction:
    def execute(self, **kwargs: Any) -> str:
        message = kwargs.get("message", "Completed")
        return f"RETURN action recognized with message: {message}"


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
        "RETURN": "return",
    }

    def __init__(self, container: punq.Container):
        self._container = container
        self._standalone_actions = {InvokeAction, PruneAction, ConcludeAction}
        self._action_map: Dict[str, Type] = {
            "execute": IShellExecutor,
            "create_file": IFileSystemManager,
            "edit": IFileSystemManager,
            "read_file": IFileSystemManager,
            "chat_with_user": IUserInteractor,
            "research": IWebSearcher,
            "invoke": InvokeAction,
            "prune": PruneAction,
            "return": ConcludeAction,
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

    def _create_read_action(self, params: Optional[dict] = None) -> IAction:
        """Handles the special routing for the READ action."""
        safe_params = params or {}
        resource = safe_params.get("resource", safe_params.get("path", ""))
        if resource.startswith("http"):
            action_handler = self._container.resolve(IWebScraper)
            setattr(
                action_handler,
                "execute",
                lambda **kwargs: action_handler.get_content(url=kwargs["path"]),
            )
            return action_handler
        # Fall through to the standard file system handler for local files
        return self._create_standard_action("read_file", params)

    def _create_standard_action(
        self, action_type: str, params: Optional[dict] = None
    ) -> IAction:
        """Creates an action handler for any action other than 'read'."""
        action_type_key = self._normalize_action_type(action_type)
        if action_type_key not in self._action_map:
            raise ValueError(f"Unknown action type: '{action_type}'")

        adapter_protocol = self._action_map[action_type_key]
        if adapter_protocol in self._standalone_actions:
            return adapter_protocol()

        action_handler = self._container.resolve(adapter_protocol)

        method_map = {
            "create_file": "create_file",
            "edit": "edit_file",
            "read_file": "read_file",
            "chat_with_user": "ask_question",
            "research": "search",
            "execute": "execute",
        }

        if action_type_key not in method_map:
            if not hasattr(action_handler, "execute"):
                raise NotImplementedError(
                    f"Adapter for {action_type} does not have a mapped method "
                    "or a default 'execute' method."
                )
            return action_handler

        method_name = method_map[action_type_key]
        original_method = getattr(action_handler, method_name)

        def execute_wrapper(**kwargs: Any) -> Any:
            if "resource" in kwargs and "path" not in kwargs:
                kwargs["path"] = kwargs.pop("resource")
            if method_name == "execute":
                execute_params = {
                    k: v
                    for k, v in kwargs.items()
                    if k in ("command", "cwd", "env") and v is not None
                }
                if "command" not in execute_params:
                    raise ValueError(
                        "'command' parameter is required for the execute action."
                    )
                return original_method(**execute_params)
            return original_method(**kwargs)

        setattr(action_handler, "execute", execute_wrapper)
        return action_handler

    def create_action(self, action_type: str, params: Optional[dict] = None) -> IAction:
        """
        Looks up the adapter protocol for the given action type and asks the
        container to resolve an instance of it. It then binds the correct
        adapter method to the `execute` method required by the IAction protocol.
        """
        if action_type.lower() == "read":
            return self._create_read_action(params)
        return self._create_standard_action(action_type, params)
