from typing import Any, Dict, List, Optional, Protocol
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.llm_client import ILlmClient, LlmApiError


class IOpenRouterHydrator(Protocol):
    """
    Internal adapter-layer port for fetching live model metadata from OpenRouter.
    """

    def get_metadata(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches metadata for a model from OpenRouter.
        Returns a dict with 'context_window' and 'pricing' if found, else None.
        """
        ...


class LiteLLMAdapter(ILlmClient):
    """
    Implements ILlmClient using the litellm library, driven by configuration.
    """

    def __init__(self, config_service: IConfigService):
        self._config_service = config_service
        self._litellm_initialized = False
        self._litellm_module: Any = None
        self._encoding: Any = None
        self._encoding_model: Optional[str] = None
        from threading import Lock

        self._init_lock = Lock()

    def _get_litellm(self) -> Any:
        """Lazily imports and silences litellm once."""
        if not self._litellm_initialized:
            with self._init_lock:
                if not self._litellm_initialized:
                    import litellm

                    self._ensure_silence(litellm)
                    self._litellm_module = litellm
                    self._litellm_initialized = True
        return self._litellm_module

    def _get_encoding(self, model: str) -> Any:
        """Lazily retrieves and caches the tiktoken encoding for a model."""
        if self._encoding_model != model:
            with self._init_lock:
                if self._encoding_model != model:
                    import tiktoken

                    try:
                        self._encoding = tiktoken.encoding_for_model(model)
                    except KeyError:
                        # Fallback for unknown models
                        self._encoding = tiktoken.get_encoding("cl100k_base")
                    self._encoding_model = model
        return self._encoding

    def _ensure_silence(self, litellm_module: Any) -> None:
        """Internal helper to silence litellm lazily."""
        import logging

        litellm_module.set_verbose = False
        litellm_module.suppress_debug_info = True
        logging.getLogger("LiteLLM").setLevel(logging.WARNING)

    def _resolve_model(self, model_override: Optional[str] = None) -> str:
        """Resolves the model name from override, config, or default."""
        resolved = model_override or self._config_service.get_setting("llm.model")
        if not resolved:
            # Fallback to a common encoding if no model is known yet
            resolved = "gpt-4o"
        return str(resolved)

    def get_completion(
        self, messages: List[Dict[str, str]], model: Optional[str] = None, **kwargs: Any
    ) -> Any:
        """
        Sends a request to an LLM via litellm and returns the raw response object.
        Values in the 'llm' section of the config are passed directly to LiteLLM.
        """
        import litellm
        from typing import cast

        # 1. Start with caller-provided kwargs
        final_params = {**kwargs}

        # 2. Explicit model argument
        if model:
            final_params["model"] = model

        # 3. Layer in 'llm' config block (Config overrides Caller/Args for control)
        llm_config = cast(Dict[str, Any], self._config_service.get_setting("llm", {}))
        final_params.update(llm_config)

        if "model" not in final_params:
            raise LlmApiError(
                "No LLM model specified. Please set 'llm.model' in your config "
                "or export 'OPENAI_API_KEY' etc. for LiteLLM defaults."
            )

        self._ensure_silence(litellm)
        from teddy_executor.core.domain.models.exceptions import ConfigurationError

        try:
            return litellm.completion(messages=messages, **final_params)
        except Exception as e:
            msg = str(e)
            # Detect common "Invalid/Expired Key" signatures
            if any(
                hint in msg
                for hint in ["API key expired", "API_KEY_INVALID", "invalid_api_key"]
            ):
                # Extract the clean message if possible, or use a generic one
                clean_msg = msg.split(" - ")[-1] if " - " in msg else msg
                raise ConfigurationError(clean_msg) from e

            raise LlmApiError(f"LLM Completion failed: {msg}") from e

    def get_token_count(
        self, messages: List[Dict[str, str]], model: Optional[str] = None
    ) -> int:
        """Calculates the number of tokens in the payload."""
        litellm = self._get_litellm()
        resolved_model = self._resolve_model(model)
        return litellm.token_counter(model=resolved_model, messages=messages)

    def get_text_token_count(self, text: str, model: Optional[str] = None) -> int:
        """Calculates the number of tokens for a raw string using tiktoken directly."""
        if not text:
            return 0
        resolved_model = self._resolve_model(model)
        encoding = self._get_encoding(resolved_model)
        return len(encoding.encode(text, disallowed_special=()))

    def get_completion_cost(self, completion_response: Any) -> float:
        """Calculates the precise USD cost of a completion response."""
        import litellm

        self._ensure_silence(litellm)
        return float(litellm.completion_cost(completion_response=completion_response))

    def validate_config(self, include_remote: bool = False) -> List[str]:
        """
        Validates the LLM configuration for common errors.
        - Checks for the default 'your-api-key' placeholder.
        - Checks for missing provider-specific environment variables.
        - Optionally performs a lightweight remote connectivity check.
        """
        import litellm

        self._ensure_silence(litellm)
        api_key = self._config_service.get_setting("llm.api_key")
        is_placeholder = isinstance(api_key, str) and api_key.lower() == "your-api-key"

        # 1. Short-circuit: Explicit placeholder needs replacement
        if is_placeholder:
            return ["'llm.api_key' is still set to the default placeholder."]

        # 2. Secondary Check: Environment/Provider requirements
        model = self._config_service.get_setting("llm.model")
        if not model:
            return ["'llm.model' is not configured."]

        errors = []
        validation_result = litellm.validate_environment(model=model)
        missing_keys = validation_result.get("missing_keys", [])

        # If a valid api_key is provided in config, we ignore missing *_API_KEY env vars
        is_api_key_provided = api_key and not is_placeholder

        for key in missing_keys:
            if is_api_key_provided and "_API_KEY" in key:
                continue
            errors.append(f"Missing required environment variable or config: {key}")

        # 3. Optional Remote Check: Verify key validity/expiration
        if not errors and include_remote:
            if not litellm.check_valid_key(model=model, api_key=api_key):
                errors.append(
                    "The API key appears to be invalid, expired, or deactivated."
                )

        return errors

    def get_context_window(self, model: Optional[str] = None) -> int:
        """
        Returns the maximum context window size (tokens) for the specified model.
        """
        import litellm

        resolved_model = model or self._config_service.get_setting("llm.model")
        if not resolved_model:
            return 0

        self._ensure_silence(litellm)
        model_info = litellm.model_cost.get(str(resolved_model), {})

        # Heuristic: max_input_tokens is specific to the context window.
        # max_tokens often refers to the output limit but is used as a fallback in litellm metadata.
        return int(
            model_info.get("max_input_tokens") or model_info.get("max_tokens") or 0
        )
