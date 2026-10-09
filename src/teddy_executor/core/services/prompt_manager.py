from importlib import resources
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.utils.serialization import scrub_dict_for_serialization

# The bundled Markdown Response Protocol base prompt. It lives OUTSIDE
# ``config/prompts/`` so it is never grouped with the user-overridable agent
# prompts, and is loaded as a package resource rather than via the file system
# port.
_MRP_PACKAGE = "teddy_executor.resources"
_MRP_FILENAME = "MRP.xml"


class PromptManager(IPromptManager):
    """
    Service for resolving agent configuration, system prompts, and user messages.
    """

    def __init__(
        self,
        file_system_manager: IFileSystemManager,
        user_interactor: IUserInteractor = None,  # type: ignore
        mrp_resource_root: Any = None,
    ):
        self._file_system_manager = file_system_manager
        self._user_interactor = user_interactor
        # Injectable resource seam: a Traversable (or any object exposing the
        # ``Traversable`` contract — ``is_file`` + ``read_text``) that anchors
        # ``MRP.xml``. When ``None``, the bundled package resource is resolved
        # lazily. Tests inject a real ``pathlib.Path`` to avoid global patching.
        self._mrp_resource_root = mrp_resource_root

    def get_prompt_content(self, agent_name: str) -> Optional[str]:
        """Synchronously retrieves the raw content of an agent prompt."""
        from teddy_executor.prompts import find_prompt_content

        return find_prompt_content(agent_name)

    def get_available_agents(self) -> list[str]:
        """Returns the list of available agent names from .teddy/prompts/."""
        prompts_dir = ".teddy/prompts/"
        if not self._file_system_manager.path_exists(prompts_dir):
            return []
        files = self._file_system_manager.list_directory(prompts_dir)
        return sorted((Path(f).stem for f in files), key=str.casefold)

    def resolve_agent_metadata(
        self, turn_path: Path
    ) -> tuple[str, Dict[str, Any], str]:
        meta_file_path = (turn_path / "meta.yaml").as_posix()
        meta_content = ""
        if self._file_system_manager.path_exists(meta_file_path):
            meta_content = self._file_system_manager.read_file(meta_file_path)

        meta = yaml.safe_load(str(meta_content))
        if not isinstance(meta, dict):
            meta = {}
        return meta.get("agent_name", "pathfinder"), meta, meta_file_path

    def resolve_message(
        self, user_message: Optional[str], turn_path: Path
    ) -> Optional[str]:
        # If message is an empty string, it's a continuation signal.
        if user_message == "":
            return ""

        resolved = user_message
        if resolved is None and turn_path.name == "01":
            # Check for initial_request.md at session root (turn_path.parent)
            # This only acts as a fallback for the very first turn.
            request_path = (turn_path.parent / "initial_request.md").as_posix()
            if self._file_system_manager.path_exists(request_path):
                resolved = self._file_system_manager.read_file(request_path)

        if resolved is not None and not resolved.strip():
            # User provided empty input at the prompt (just hit enter) -> Exit
            return None

        return resolved

    def _find_prompt_file(self, directory: str, agent_name: str) -> Optional[str]:
        """Searches a directory for a file with the given agent name (any extension)."""
        if not self._file_system_manager.path_exists(directory):
            return None
        for f in self._file_system_manager.list_directory(directory):
            if Path(f).stem.casefold() == agent_name.casefold():
                return f"{directory}/{f}"
        return None

    def _resolve_agent_prompt_content(self, agent_name: str, turn_path: Path) -> str:
        """Resolves the agent-specific prompt XML from the canonical
        ``.teddy/prompts/`` directory (the user-editable source).

        Returns an empty string (with a warning) when no prompt file is found,
        preserving the graceful-degradation contract. Session-root prompts are
        resolved by the caller (``fetch_system_prompt``), which returns them
        verbatim rather than re-composing them.
        """
        teddy_prompt_dir = (
            turn_path.parent.parent.parent.parent / ".teddy" / "prompts"
        ).as_posix()
        teddy_prompt_path = self._find_prompt_file(teddy_prompt_dir, agent_name)
        if teddy_prompt_path:
            return self._file_system_manager.read_file(teddy_prompt_path)

        logging.getLogger(__name__).warning(
            "PromptManager: Failed to resolve system prompt for agent '%s' (searched %s)",
            agent_name,
            teddy_prompt_path,
        )
        return ""

    def _load_mrp_base_prompt(self) -> str:
        """Loads the bundled Markdown Response Protocol base prompt.

        Uses only the ``Traversable`` contract (``is_file`` + ``read_text``) so
        it works both in a source checkout (``pathlib.Path``) and under a
        zip/wheel install (``zipfile.Path``). Fails fast when the resource is
        absent to prevent silent protocol degradation.
        """
        root = self._mrp_resource_root
        if root is None:
            root = resources.files(_MRP_PACKAGE)
        resource = root / _MRP_FILENAME
        if not resource.is_file():
            raise FileNotFoundError(
                f"Bundled MRP base prompt not found at {resource}. "
                f"The package resource '{_MRP_PACKAGE}/{_MRP_FILENAME}' is missing."
            )
        return resource.read_text(encoding="utf-8")

    def fetch_system_prompt(self, agent_name: str, turn_path: Path) -> str:
        # Option A: the session-root prompt file IS the composed system prompt
        # (written by SessionService at session creation / agent switch). Return
        # it verbatim -- never re-compose, to avoid a duplicate header and MRP.
        session_root_prompt = self._find_prompt_file(
            turn_path.parent.as_posix(), agent_name
        )
        if session_root_prompt:
            return self._file_system_manager.read_file(session_root_prompt)

        # Lazy-compose fallback (legacy session or manually deleted file):
        # assemble from the canonical ``.teddy/prompts/`` source.
        content = self._resolve_agent_prompt_content(agent_name, turn_path)
        if not content:
            # No agent prompt resolved: preserve the historical empty-string
            # contract (no header, no MRP) rather than fabricating a prompt.
            return ""

        assembled = f"Agent Name: {agent_name.capitalize()}\n\n{content}"

        # Legacy compatibility: a resolved prompt that already carries its own
        # response format (e.g. a customized ``.teddy/prompts/`` override) is
        # returned without the shared MRP block, but keeps the agent-name header.
        if "<response_format>" in content:
            return assembled

        # Both the agent-specific XML and the MRP block live inside the
        # assembled ``<system>`` prompt; MRP is appended AFTER the agent content.
        return f"{assembled}\n\n{self._load_mrp_base_prompt()}"

    def log_telemetry(self, token_count: Any, turn_cost: Any) -> float:
        def safe_float(v: Any, default: float = 0.0) -> float:
            try:
                return float(v)
            except (TypeError, ValueError):
                return default

        return safe_float(turn_cost)

    def update_meta(
        self,
        meta: Dict[str, Any],
        response: Any,
        token_count: int,
        turn_cost: float,
        meta_file_path: str,
    ) -> None:
        try:
            meta["turn_cost"] = float(turn_cost)
            meta["token_count"] = int(token_count)
        except (TypeError, ValueError):
            meta["turn_cost"] = meta.get("turn_cost", 0.0)
            meta["token_count"] = meta.get("token_count", 0)

        # Preserve the user-configured model (with routing prefix) for routing.
        # Store the actual serving model separately for telemetry.
        actual_model = str(getattr(response, "model", "unknown"))
        if "model" not in meta or meta.get("model") == actual_model:
            meta["model"] = actual_model
        meta["actual_model"] = actual_model

        # Capture finish_reason; scrub_dict_for_serialization will neutralize mocks
        if hasattr(response, "choices") and len(response.choices) > 0:
            meta["finish_reason"] = getattr(
                response.choices[0], "finish_reason", "unknown"
            )

        serializable_meta = scrub_dict_for_serialization(meta)
        self._file_system_manager.write_file(
            meta_file_path, yaml.dump(serializable_meta)
        )
