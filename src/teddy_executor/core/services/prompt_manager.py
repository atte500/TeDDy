from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.utils.serialization import scrub_dict_for_serialization


class PromptManager(IPromptManager):
    """
    Service for resolving agent configuration, system prompts, and user messages.
    """

    def __init__(
        self,
        file_system_manager: IFileSystemManager,
        user_interactor: IUserInteractor = None,  # type: ignore
    ):
        self._file_system_manager = file_system_manager
        self._user_interactor = user_interactor

    def get_prompt_content(self, agent_name: str) -> Optional[str]:
        """Synchronously retrieves the raw content of an agent prompt."""
        from teddy_executor.prompts import find_prompt_content

        return find_prompt_content(agent_name)

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

    def fetch_system_prompt(self, agent_name: str, turn_path: Path) -> str:
        # 1. Try Turn-Specific override
        prompt_file_path = (turn_path / f"{agent_name}.xml").as_posix()
        if self._file_system_manager.path_exists(prompt_file_path):
            return self._file_system_manager.read_file(prompt_file_path)

        # 2. Try Internal Resource Fallback
        resource_path = (
            Path(__file__).parent.parent.parent
            / "resources"
            / "prompts"
            / f"{agent_name}.xml"
        ).as_posix()
        if self._file_system_manager.path_exists(resource_path):
            return self._file_system_manager.read_file(resource_path)

        import logging

        logging.getLogger(__name__).warning(
            "PromptManager: Failed to resolve system prompt for agent '%s' (searched %s and %s)",
            agent_name,
            prompt_file_path,
            resource_path,
        )
        return ""

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

        if not meta.get("model"):
            meta["model"] = str(getattr(response, "model", "unknown"))

        # Capture finish_reason; scrub_dict_for_serialization will neutralize mocks
        if hasattr(response, "choices") and len(response.choices) > 0:
            meta["finish_reason"] = getattr(
                response.choices[0], "finish_reason", "unknown"
            )

        serializable_meta = scrub_dict_for_serialization(meta)
        self._file_system_manager.write_file(
            meta_file_path, yaml.dump(serializable_meta)
        )
