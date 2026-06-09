from typing import Any, Dict, Optional
from teddy_executor.core.domain.models.action_ports import ActionPorts
from teddy_executor.core.domain.models.plan import DEFAULT_SIMILARITY_THRESHOLD
from teddy_executor.core.services.action_dispatcher import IAction, IActionFactory


class ActionFactory(IActionFactory):
    """
    A protocol-compliant factory that resolves action handlers from injected ports.
    """

    # Maps uppercase verbs from Markdown plans to the internal, descriptive keys.
    _MARKDOWN_ACTION_MAP = {
        "CREATE": "create_file",
        "EDIT": "edit",
        "READ": "read",
        "EXECUTE": "execute",
        "MESSAGE": "message",
        "RESEARCH": "research",
    }

    def __init__(self, ports: ActionPorts):
        self._shell_executor = ports.shell_executor
        self._file_system_manager = ports.file_system_manager
        self._user_interactor = ports.user_interactor
        self._web_scraper = ports.web_scraper
        self._web_searcher = ports.web_searcher
        self._config_service = ports.config_service
        self._standalone_actions: set[str] = set()
        self._action_map: Dict[str, Any] = {
            "execute": self._shell_executor,
            "create_file": self._file_system_manager,
            "edit": self._file_system_manager,
            "read_file": self._file_system_manager,
            "message": self._user_interactor,
            "research": self._web_searcher,
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
            # Return a wrapper instead of monkeypatching the adapter
            class WebReadAction:
                def __init__(self, scraper):
                    self._scraper = scraper

                def execute(self, **kwargs: Any) -> Any:
                    return self._scraper.get_content(url=kwargs["path"])

            return WebReadAction(self._web_scraper)
        # Fall through to the standard file system handler for local files
        return self._create_standard_action("read_file", params)

    def _get_action_wrapper(self, handler: Any, method_name: str) -> IAction:
        """Returns an IAction wrapper around an adapter method."""
        original_method = getattr(handler, method_name)

        class ActionWrapper:
            def __init__(self, factory, method):
                self._factory = factory
                self._method = method

            def execute(self, **kwargs: Any) -> Any:
                if "resource" in kwargs and "path" not in kwargs:
                    kwargs["path"] = kwargs.pop("resource")

                if method_name == "execute":
                    return self._factory._handle_execute_protocol(self._method, kwargs)
                if method_name == "edit_file":
                    return self._factory._handle_edit_protocol(self._method, kwargs)
                if method_name == "ask_question":
                    return self._factory._handle_message_protocol(self._method, kwargs)
                return self._method(**kwargs)

        return ActionWrapper(self, original_method)

    def _handle_execute_protocol(self, method: Any, kwargs: dict) -> Any:
        """Handles the complex parameter injection for the EXECUTE action."""
        execute_params = {
            k: v
            for k, v in kwargs.items()
            if k in ("command", "cwd", "env", "background", "timeout", "max_lines")
            and v is not None
        }
        if "command" not in execute_params:
            raise ValueError("'command' parameter is required for the execute action.")

        # Extract Tail override from action params and convert to max_lines
        tail = kwargs.get("tail")
        if tail is not None:
            try:
                tail_int = int(tail)
                if tail_int > 0:
                    execute_params["max_lines"] = tail_int
            except (ValueError, TypeError):
                pass  # Invalid tail value, fall back to default

        # Inject global timeout if not already specified in kwargs
        if "timeout" not in execute_params and self._config_service:
            # Safe-by-Default: Provide hardcoded 60.0 fallback if config is missing
            default_timeout = self._config_service.get_setting(
                "execution.default_timeout_seconds", 60.0
            )
            if default_timeout is not None:
                execute_params["timeout"] = float(default_timeout)

        return method(**execute_params)

    def _handle_edit_protocol(self, method: Any, kwargs: dict) -> Any:
        """Handles the similarity threshold injection for the EDIT action."""
        # 1. Inject from config if missing
        if "similarity_threshold" not in kwargs and self._config_service:
            # Safe-by-Default: Provide domain default if config is missing
            global_threshold = self._config_service.get_setting(
                "execution.similarity_threshold", DEFAULT_SIMILARITY_THRESHOLD
            )
            if global_threshold is not None:
                kwargs["similarity_threshold"] = float(global_threshold)
        return method(**kwargs)

    def _handle_message_protocol(self, method: Any, kwargs: dict) -> Any:
        """Handles the positional argument mapping for the MESSAGE action."""
        prompt = kwargs.get("prompt", kwargs.get("content", "")) or ""
        return method(
            prompt,
            resources=kwargs.get("handoff_resources"),
            agent_name=kwargs.get("agent_name"),
        )

    def _create_standard_action(
        self, action_type: str, params: Optional[dict] = None
    ) -> IAction:
        """Creates an action handler for any action other than 'read'."""
        action_type_key = self._normalize_action_type(action_type)
        if action_type_key not in self._action_map:
            raise ValueError(f"Unknown action type: '{action_type}'")

        action_handler = self._action_map[action_type_key]
        if action_handler in self._standalone_actions:
            return action_handler()

        method_map = {
            "create_file": "create_file",
            "edit": "edit_file",
            "read_file": "read_file",
            "message": "ask_question",
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

        return self._get_action_wrapper(action_handler, method_map[action_type_key])

    def create_action(self, action_type: str, params: Optional[dict] = None) -> IAction:
        """
        Looks up the adapter protocol for the given action type and binds the correct
        adapter method to the `execute` method required by the IAction protocol.
        """
        if action_type.lower() == "read":
            return self._create_read_action(params)
        return self._create_standard_action(action_type, params)
