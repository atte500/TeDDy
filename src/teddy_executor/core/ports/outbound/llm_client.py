from abc import ABC, abstractmethod
from typing import Any, Dict, List


class LlmApiError(Exception):
    """Raised for any failures during an LLM API call."""

    pass


class ILlmClient(ABC):
    """
    Generic interface for communicating with a Large Language Model.
    """

    @abstractmethod
    def get_completion(
        self, model: str, messages: List[Dict[str, str]], **kwargs: Any
    ) -> str:
        """
        Sends a request to an LLM and returns the completed text response.

        Args:
            model: The identifier for the target model.
            messages: A list of message dictionaries (role/content).
            **kwargs: Additional parameters for the LLM provider.

        Returns:
            The string content of the LLM's response.

        Raises:
            LlmApiError: For any failures during the API call.
        """
        pass
