from abc import ABC, abstractmethod
from typing import Optional, Dict
from teddy_executor.core.domain.models import CommandResult


class IShellExecutor(ABC):
    """
    Defines the contract for executing a shell command.
    """

    @abstractmethod
    def execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> CommandResult:
        """
        Executes a shell command and returns its result.
        """
        pass
