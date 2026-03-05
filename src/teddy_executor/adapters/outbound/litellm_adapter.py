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

        # Merge all config values into kwargs, prioritizing call-time kwargs
        # This allows users to set 'api_key', 'api_base', 'custom_llm_provider', etc.
        for key, value in llm_config.items():
            if key not in kwargs:
                kwargs[key] = value

        # The 'model' from the method argument takes precedence over config
        if "model" not in kwargs or model:
            kwargs["model"] = model

        try:
            response = litellm.completion(messages=messages, **kwargs)
            if hasattr(response, "choices") and len(response.choices) > 0:
                return response.choices[0].message.content or ""
            return ""
        except Exception as e:
            raise LlmApiError(f"LLM Completion failed: {str(e)}") from e
