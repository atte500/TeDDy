from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class LlmApiError(Exception):
    """Raised for any failures during an LLM API call."""

    pass


class ILlmClient(ABC):
    """
    Generic interface for communicating with a Large Language Model.
    """

    @abstractmethod
    def get_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        """
        Sends a request to an LLM and returns the completed response object.

        Args:
            messages: A list of message dictionaries (role/content).
            model: Optional identifier for the target model (overrides config).
            **kwargs: Additional parameters for the LLM provider.

        Returns:
            The string content of the LLM's response.

        Raises:
            LlmApiError: For any failures during the API call.
        """
        pass

    @abstractmethod
    def get_token_count(
        self, messages: List[Dict[str, str]], model: Optional[str] = None
    ) -> int:
        """
        Calculates the number of tokens in the payload.
        """
        pass

    @abstractmethod
    def get_completion_cost(self, _completion_response: Any) -> float:
        """
        Calculates the precise USD cost of a completion response.
        """
        pass

    @abstractmethod
    def validate_config(self, _include_remote: bool = False) -> List[str]:
        """
        Validates the current configuration (API keys, models, etc.).
        If _include_remote is True, performs a lightweight connectivity check.

        Returns:
            A list of error messages. An empty list indicates valid configuration.
        """
        pass

    @abstractmethod
    def get_context_window(self, model: Optional[str] = None) -> int:
        """
        Returns the maximum context window size (tokens) for the specified model.
        Returns 0 if the limit is unknown.
        """
        pass
