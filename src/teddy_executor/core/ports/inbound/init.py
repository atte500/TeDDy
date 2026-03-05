from abc import ABC, abstractmethod


class IInitUseCase(ABC):
    """
    Inbound port for project initialization.
    """

    @abstractmethod
    def ensure_initialized(self) -> None:
        """
        Ensures the .teddy/ directory and its essential configuration
        files are present in the current project root.
        """
        pass
