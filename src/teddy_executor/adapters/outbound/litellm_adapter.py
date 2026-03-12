from typing import Any, Dict, List
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.llm_client import ILlmClient, LlmApiError


class LiteLLMAdapter(ILlmClient):
    """
    Implements ILlmClient using the litellm library, driven by configuration.
    """

    def __init__(self, config_service: IConfigService):
        self._config_service = config_service
        self._silence_litellm()

    def _silence_litellm(self) -> None:
        """
        Configures LiteLLM to be quiet.
        Note: This method is now empty to prevent LiteLLM import during initialization.
        Silencing is handled lazily within the methods that use the library.
        """
        pass

    def _ensure_silence(self, litellm_module: Any) -> None:
        """Internal helper to silence litellm lazily."""
        import logging

        litellm_module.set_verbose = False
        litellm_module.suppress_debug_info = True
        logging.getLogger("LiteLLM").setLevel(logging.WARNING)

    def get_completion(
        self, model: str, messages: List[Dict[str, str]], **kwargs: Any
    ) -> Any:
        """
        Sends a request to an LLM via litellm and returns the raw response object.
        Values in the 'llm' section of the config are passed directly to LiteLLM.
        """
        import litellm
        from typing import cast

        # Retrieve LLM settings from config
        llm_config = cast(Dict[str, Any], self._config_service.get_setting("llm", {}))

        # Apply caller-provided model
        if model:
            kwargs["model"] = model

        # Merge config values into kwargs, prioritizing config values over caller-provided ones
        # This allows users to globally override 'model', 'api_key', etc. via config.yaml
        for key, value in llm_config.items():
            kwargs[key] = value

        self._ensure_silence(litellm)
        try:
            return litellm.completion(messages=messages, **kwargs)
        except Exception as e:
            raise LlmApiError(f"LLM Completion failed: {str(e)}") from e

    def get_token_count(self, model: str, messages: List[Dict[str, str]]) -> int:
        """Calculates the number of tokens in the payload."""
        import litellm

        self._ensure_silence(litellm)
        return litellm.token_counter(model=model, messages=messages)

    def get_completion_cost(self, completion_response: Any) -> float:
        """Calculates the precise USD cost of a completion response."""
        import litellm

        self._ensure_silence(litellm)
        return float(litellm.completion_cost(completion_response=completion_response))
