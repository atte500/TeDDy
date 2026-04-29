from typing import Any, Dict, List, Optional
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
        self, messages: List[Dict[str, str]], model: Optional[str] = None, **kwargs: Any
    ) -> Any:
        """
        Sends a request to an LLM via litellm and returns the raw response object.
        Values in the 'llm' section of the config are passed directly to LiteLLM.
        """
        import litellm
        from typing import cast

        # 1. Start with values from 'llm' config block
        llm_config = cast(Dict[str, Any], self._config_service.get_setting("llm", {}))
        final_params = {**llm_config}

        # 2. Layer in caller-provided kwargs
        final_params.update(kwargs)

        # 3. Explicit model override
        if model:
            final_params["model"] = model

        if "model" not in final_params:
            raise LlmApiError(
                "No LLM model specified. Please set 'llm.model' in your config "
                "or export 'OPENAI_API_KEY' etc. for LiteLLM defaults."
            )

        self._ensure_silence(litellm)
        try:
            return litellm.completion(messages=messages, **final_params)
        except Exception as e:
            raise LlmApiError(f"LLM Completion failed: {str(e)}") from e

    def get_token_count(
        self, messages: List[Dict[str, str]], model: Optional[str] = None
    ) -> int:
        """Calculates the number of tokens in the payload."""
        import litellm

        resolved_model = model or self._config_service.get_setting("llm.model")
        if not resolved_model:
            # Fallback to a common encoding if no model is known yet
            resolved_model = "gpt-4o"

        self._ensure_silence(litellm)
        return litellm.token_counter(model=str(resolved_model), messages=messages)

    def get_completion_cost(self, completion_response: Any) -> float:
        """Calculates the precise USD cost of a completion response."""
        import litellm

        self._ensure_silence(litellm)
        return float(litellm.completion_cost(completion_response=completion_response))
