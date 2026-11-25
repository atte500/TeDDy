import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from teddy_executor.core.domain.models.action_ports import ActionPorts
from teddy_executor.core.domain.models.plan import DEFAULT_SIMILARITY_THRESHOLD
from teddy_executor.core.services.action_dispatcher import IAction, IActionFactory
from teddy_executor.core.services.parser_infrastructure import coerce_param
from teddy_executor.core.utils.pdf import cap_extracted_text, is_pdf_source

if TYPE_CHECKING:
    from teddy_executor.core.services.web_content_service import WebContentService


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

    def __init__(
        self,
        ports: ActionPorts,
        web_content_service: Optional["WebContentService"] = None,
    ):
        self._shell_executor = ports.shell_executor
        self._file_system_manager = ports.file_system_manager
        self._user_interactor = ports.user_interactor
        self._web_searcher = ports.web_searcher
        self._config_service = ports.config_service
        self._pdf_extractor = ports.pdf_extractor
        self._web_content_service = web_content_service
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

    def _create_read_action(
        self, params: Optional[dict] = None, session_root: Optional[str] = None
    ) -> IAction:
        """Handles the special routing for the READ action."""
        safe_params = params or {}
        resource = safe_params.get("resource", safe_params.get("path", ""))
        if resource.startswith("http"):
            fetch = self._url_fetcher(session_root)

            # Return a wrapper instead of monkeypatching the adapter
            class WebReadAction:
                def __init__(self, fetcher):
                    self._fetcher = fetcher

                def execute(self, **kwargs: Any) -> Any:
                    try:
                        return self._fetcher(kwargs["path"])
                    except Exception as e:
                        logging.getLogger(__name__).debug(
                            "Failed to fetch URL '%s': %s", kwargs.get("path"), e
                        )
                        return f"Error: Failed to fetch URL ({e})"

            return WebReadAction(fetch)

        if is_pdf_source(resource):
            return self._create_pdf_read_action()

        if safe_params.get("lines"):
            # Lines-aware read: use read_raw_file (bypass truncation) and extract range
            from teddy_executor.core.utils.string import extract_lines_range  # noqa: PLC0415

            class LinesAwareReadAction:
                def __init__(self, fs):
                    self._fs = fs

                def execute(self, **kwargs: Any) -> Any:
                    path = kwargs.get("path", kwargs.get("resource", ""))
                    content = self._fs.read_raw_file(path=path)
                    lines_spec = kwargs.get("lines", "")
                    return extract_lines_range(content, lines_spec)

            return LinesAwareReadAction(self._file_system_manager)

        # Fall through to the standard file system handler for local files
        return self._create_standard_action("read_file", params)

    def _url_fetcher(self, session_root: Optional[str]) -> Callable[[str], str]:
        """Binds the coordinator's cached read to the creation-time session root.

        A remote read has no other route: the coordinator owns the session cache
        and the announced cap, so a factory built without one cannot serve a URL.
        """
        coordinator = self._web_content_service
        assert coordinator is not None, (
            "web_content_service is required for a READ on a URL"
        )
        return lambda url: coordinator.fetch_one(url, session_root=session_root)

    def _create_pdf_read_action(self) -> IAction:
        """Builds a READ handler that extracts text from a local PDF payload."""
        fs = self._file_system_manager
        extractor = self._pdf_extractor
        assert extractor is not None, (
            "pdf_extractor port is required for a local PDF read"
        )
        max_lines = self._resolve_read_max_lines()

        class PdfReadAction:
            def execute(self, **kwargs: Any) -> Any:
                path = kwargs.get("path", kwargs.get("resource", ""))
                data = fs.read_file_bytes(path=path)
                text = extractor.extract_text(data, source=path)
                if max_lines is None:
                    return text
                return cap_extracted_text(text, max_lines)

        return PdfReadAction()

    def _resolve_read_max_lines(self) -> Optional[int]:
        """Resolves the shared ``read.max_lines`` budget, or ``None`` when unset."""
        if not self._config_service:
            return None
        raw = self._config_service.get_setting("read.max_lines", None)
        coerced = coerce_param(raw, int)
        if not isinstance(coerced, int) or coerced <= 0:
            return None
        return coerced

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
                "execute.default_timeout_seconds", 60.0
            )
            if default_timeout is not None:
                coerced = coerce_param(default_timeout, float)
                if coerced is not None:
                    execute_params["timeout"] = coerced

        return method(**execute_params)

    def _handle_edit_protocol(self, method: Any, kwargs: dict) -> Any:
        """Handles the similarity threshold injection for the EDIT action."""
        # 1. Inject from config if missing
        if "similarity_threshold" not in kwargs and self._config_service:
            # Safe-by-Default: Provide domain default if config is missing
            global_threshold = self._config_service.get_setting(
                "edit.similarity_threshold", DEFAULT_SIMILARITY_THRESHOLD
            )
            if global_threshold is not None:
                coerced = coerce_param(global_threshold, float)
                if coerced is not None:
                    kwargs["similarity_threshold"] = coerced
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

    def create_action(
        self,
        action_type: str,
        params: Optional[dict] = None,
        session_root: Optional[str] = None,
    ) -> IAction:
        """
        Looks up the adapter protocol for the given action type and binds the correct
        adapter method to the `execute` method required by the IAction protocol.
        """
        if action_type.lower() == "read":
            return self._create_read_action(params, session_root=session_root)
        return self._create_standard_action(action_type, params)
