from abc import ABC, abstractmethod
from teddy_executor.core.domain.models import CommandResult


class ShellExecutor(ABC):
    """
    Defines the contract for executing a shell command.
    """

    @abstractmethod
    def run(self, command: str) -> CommandResult:
        """
        Executes a shell command and returns its result.
        """
        pass
