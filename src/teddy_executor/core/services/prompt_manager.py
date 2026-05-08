from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.utils.markdown import extract_markdown_section
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

    def _ensure_alignment_hint(
        self, message: str, default: Optional[str] = None
    ) -> str:
        if not message or not message.strip():
            return default or ""

        hint = "\n\n*(Stop to reply to this user request and ensure alignment before proceeding)*"
        if hint not in message and "(No instructions provided" not in message:
            return message + hint
        return message

    def resolve_message(
        self, user_message: Optional[str], turn_path: Path
    ) -> Optional[str]:
        # R-10-12: If message is an empty string, it's a continuation signal.
        if user_message == "":
            return ""

        resolved = user_message
        if resolved is None:
            report_path = (turn_path / "report.md").as_posix()
            if self._file_system_manager.path_exists(report_path):
                report_content = self._file_system_manager.read_file(report_path)
                resolved = extract_markdown_section(report_content, "User Request")

        if resolved is None and self._user_interactor:
            resolved = self._user_interactor.ask_question(
                "Enter your instructions for the AI"
            )

        if resolved is not None and not resolved.strip():
            # User provided empty input at the prompt (just hit enter) -> Exit
            return None

        if resolved is None:
            return None

        return self._ensure_alignment_hint(resolved)

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

        meta["model"] = str(getattr(response, "model", "unknown"))

        # R-10-12: Capture finish_reason to diagnose empty responses (safety/filter/length)
        if hasattr(response, "choices") and len(response.choices) > 0:
            meta["finish_reason"] = getattr(
                response.choices[0], "finish_reason", "unknown"
            )

        serializable_meta = scrub_dict_for_serialization(meta)
        self._file_system_manager.write_file(
            meta_file_path, yaml.dump(serializable_meta)
        )
