from typing import Any, Dict, List
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.llm_client import ILlmClient, LlmApiError


class LiteLLMAdapter(ILlmClient):
    """
    Implements ILlmClient using the litellm library, driven by configuration.
    """

    def __init__(self, config_service: IConfigService):
        self._config_service = config_service

    def get_completion(
        self, model: str, messages: List[Dict[str, str]], **kwargs: Any
    ) -> str:
        """
        Sends a request to an LLM via litellm and returns the text response.
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

        try:
            response = litellm.completion(messages=messages, **kwargs)
            if hasattr(response, "choices") and len(response.choices) > 0:
                return response.choices[0].message.content or ""
            return ""
        except Exception as e:
            raise LlmApiError(f"LLM Completion failed: {str(e)}") from e

    def get_token_count(self, model: str, messages: List[Dict[str, str]]) -> int:
        """Stub for token count calculation."""
        return 0

    def get_completion_cost(self, _completion_response: Any) -> float:
        """Stub for completion cost calculation."""
        return 0.0
