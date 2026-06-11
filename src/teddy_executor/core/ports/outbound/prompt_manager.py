from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional


class IPromptManager(ABC):
    """
    Port for resolving agent configuration, system prompts, and user messages.
    """

    @abstractmethod
    def get_available_agents(self) -> list[str]:
        """Returns the list of available agent names (prompt files)."""
        ...

    @abstractmethod
    def get_prompt_content(self, _agent_name: str) -> Optional[str]:
        """Synchronously retrieves the raw content of an agent prompt."""
        ...

    @abstractmethod
    def resolve_agent_metadata(
        self, _turn_path: Path
    ) -> tuple[str, Dict[str, Any], str]:
        """Resolves agent name and metadata from meta.yaml."""
        ...

    @abstractmethod
    def resolve_message(
        self, _user_message: Optional[str], _turn_path: Path
    ) -> Optional[str]:
        """Synchronously resolves the user message with alignment hints."""
        ...

    @abstractmethod
    def fetch_system_prompt(self, _agent_name: str, _turn_path: Path) -> str:
        """Synchronously fetches the system prompt for the agent."""
        ...

    @abstractmethod
    def log_telemetry(self, _token_count: Any, _turn_cost: Any) -> float:
        """Logs planning telemetry."""
        ...

    @abstractmethod
    def update_meta(
        self,
        _meta: Dict[str, Any],
        _response: Any,
        _token_count: int,
        _turn_cost: float,
        _meta_file_path: str,
    ) -> None:
        """Updates and persists turn metadata."""
        ...
