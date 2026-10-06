import logging
from typing import Any, Dict, List, Optional, Protocol
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.domain.models.exceptions import ConfigurationError
from teddy_executor.core.ports.outbound.llm_client import ILlmClient, LlmApiError
from teddy_executor.core.ports.outbound.time_service import ITimeService

logger = logging.getLogger(__name__)


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

    def __init__(
        self,
        config_service: IConfigService,
        hydrator: Optional[IOpenRouterHydrator] = None,
        time_service: Optional[ITimeService] = None,
        _litellm_provider: Optional[Any] = None,
    ):
        self._config_service = config_service
        self._hydrator = hydrator
        self._time_service = time_service
        self._litellm_initialized = _litellm_provider is not None
        self._litellm_module: Any = _litellm_provider
        self._encoding: Any = None
        self._encoding_model: Optional[str] = None
        self._executor: Any = None
        self._validated: bool = False
        from threading import Lock

        self._init_lock = Lock()

    def _get_executor(self) -> Any:
        """Lazily creates a ThreadPoolExecutor for remote checks."""
        if not self._executor:
            with self._init_lock:
                if not self._executor:
                    from concurrent.futures import ThreadPoolExecutor

                    self._executor = ThreadPoolExecutor(max_workers=5)
        return self._executor

    def _get_litellm(self) -> Any:
        """Lazily imports and silences litellm once."""
        if not self._litellm_initialized:
            with self._init_lock:
                if not self._litellm_initialized:
                    # Silence logging BEFORE import to suppress botocore warnings
                    self._ensure_silence(None)
                    import litellm

                    # Silence library-specific flags AFTER import
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
        import os

        # 1. Prepare environment before import or reinforce after
        os.environ["LITELLM_LOG"] = "CRITICAL"
        logging.getLogger("LiteLLM").setLevel(logging.CRITICAL)

        # 2. Configure module-specific flags if provided
        if litellm_module:
            litellm_module.set_verbose = False
            litellm_module.suppress_debug_info = True

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
        litellm = self._get_litellm()

        # Lazy validation guard: validate config on first invocation
        if not self._validated:
            with self._init_lock:
                if not self._validated:
                    errors = self.validate_config()
                    if errors:
                        raise ConfigurationError(errors[0])
                    self._validated = True

        final_params = self._prepare_completion_params(model, **kwargs)

        # Lazy startup validation: check config on first call only
        if not self._validated:
            with self._init_lock:
                if not self._validated:
                    from teddy_executor.core.domain.models.exceptions import (
                        ConfigurationError as _ConfigError,
                    )

                    errors = self.validate_config()
                    if errors:
                        raise _ConfigError(errors[0])
                    self._validated = True

        max_attempts_val = final_params.get("max_retries")
        max_attempts = int(max_attempts_val) if max_attempts_val is not None else 3
        last_exception: Optional[Exception] = None

        for attempt in range(max_attempts):
            try:
                return litellm.completion(messages=messages, **final_params)
            except Exception as e:
                last_exception = e
                response = self._handle_hydration_retry(e, messages, final_params)
                if response:
                    return response

                if self._should_retry_completion(e, attempt, max_attempts):
                    continue

                self._raise_specific_completion_errors(e)
                break

        final_msg = str(last_exception) if last_exception else "Unknown error"
        raise LlmApiError(f"LLM Completion failed: {final_msg}") from last_exception

    def _prepare_completion_params(
        self, model: Optional[str] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        """Resolves and layers configuration for the completion request."""
        from typing import cast

        params = {**kwargs}

        llm_config = cast(Dict[str, Any], self._config_service.get_setting("llm", {}))
        params.update(llm_config)

        # Drop an empty/blank api_key so litellm applies the provider's own
        # default (e.g. a dummy key for keyless local models). Forwarding "" is
        # equivalent to a missing key and raises AuthenticationError.
        api_key = params.get("api_key")
        if isinstance(api_key, str) and not api_key.strip():
            del params["api_key"]

        if model:
            params["model"] = model

        # Default timeout of 300 seconds if not configured
        if "timeout" not in params:
            params["timeout"] = 300

        if "model" not in params:
            raise LlmApiError(
                "No LLM model specified. Please set 'llm.model' in your config."
            )

        return params

    _AUTH_ERROR_HINTS = [
        "API key expired",
        "API_KEY_INVALID",
        "invalid_api_key",
        "api_key client option must be set",
        "Incorrect API key",
        "No cookie auth credentials",
    ]

    def _is_auth_error(self, error: Exception) -> bool:
        """Detects authentication/key errors by message hint OR exception TYPE.

        Auth failures are NOT transient: no amount of retrying will fix a wrong
        or expired key, so they must fail fast. Detection is two-pronged because
        a provider's exact wording is not load-bearing. The type check is guarded
        by ``isinstance(candidate, type)`` so the dynamically-created attributes
        of a mock provider are never mistaken for the real exception class.
        """
        msg = str(error)
        if any(hint in msg for hint in self._AUTH_ERROR_HINTS):
            return True
        candidate = getattr(self._get_litellm(), "AuthenticationError", None)
        return isinstance(candidate, type) and isinstance(error, candidate)

    def _should_retry_completion(
        self, error: Exception, attempt: int, max_attempts: int
    ) -> bool:
        """Retries transient errors with exponential backoff; never auth errors.

        Authentication errors are permanent, so they are surfaced immediately
        (fail fast) instead of burning the backoff budget on calls that cannot
        succeed. All other exceptions keep the retry-on-any-error behaviour,
        since config validation has already passed.
        """
        if self._is_auth_error(error):
            return False
        if attempt < max_attempts - 1:
            delay = 0.5 * (2**attempt)
            if self._time_service:
                self._time_service.sleep(delay)
            else:
                import time

                time.sleep(delay)
            return True
        return False

    def _raise_specific_completion_errors(self, error: Exception) -> None:
        """Raises a specific error based on the exception signature.

        Auth errors (by hint OR type) become a ``ConfigurationError`` with the
        original message preserved for a clear, actionable CLI message.
        """
        if self._is_auth_error(error):
            msg = str(error)
            clean_msg = msg.split(" - ")[-1] if " - " in msg else msg
            raise ConfigurationError(clean_msg) from error

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

    def get_completion_cost(
        self, completion_response: Any, model_override: Optional[str] = None
    ) -> float:
        """Calculates the precise USD cost of a completion response."""
        litellm = self._get_litellm()
        try:
            return float(
                litellm.completion_cost(completion_response=completion_response)
            )
        except (Exception, TypeError) as e:
            if "This model isn't mapped yet" in str(e) and self._hydrator:
                candidates = set()
                if model_override:
                    candidates.add(str(model_override))
                model_id = getattr(completion_response, "model", None)
                if model_id:
                    candidates.add(str(model_id))

                if self._hydrate_all_candidates(candidates):
                    try:
                        return float(
                            litellm.completion_cost(
                                completion_response=completion_response
                            )
                        )
                    except (Exception, TypeError) as retry_error:
                        self._log_cost_failure(
                            retry_error, completion_response, model_override
                        )
                        return 0.0

            # Graceful fallback for unmapped models or hydration failure
            self._log_cost_failure(e, completion_response, model_override)
            return 0.0

    def _log_cost_failure(
        self, error: Exception, completion_response: Any, model_override: Optional[str]
    ) -> None:
        """Logs a cost-computation failure with tiered severity.

        WARNING when the resolved model HAS pricing metadata yet
        ``completion_cost`` raised (an anomaly: real spend silently lost);
        DEBUG when the model is unpriced (an expected miss, mirroring the TUI
        ``$???`` placeholder). The caller still returns 0.0 so an otherwise
        successful completion is never penalised for non-critical telemetry.
        """
        model_id = self._resolve_cost_model(completion_response, model_override)
        summary = {
            "model": model_id,
            "prompt_tokens": self._extract_usage_value(
                completion_response, "prompt_tokens"
            ),
            "completion_tokens": self._extract_usage_value(
                completion_response, "completion_tokens"
            ),
            "cached_tokens": self._extract_detail_value(
                completion_response, "prompt_tokens_details", "cached_tokens"
            ),
            "reasoning_tokens": self._extract_detail_value(
                completion_response, "completion_tokens_details", "reasoning_tokens"
            ),
        }
        if self.supports_pricing(model_id):
            logger.warning(
                "Cost computation failed for priced model: %s", summary, exc_info=True
            )
        else:
            logger.debug(
                "Cost computation failed for unpriced model: %s",
                summary,
                exc_info=True,
            )

    def _resolve_cost_model(
        self, completion_response: Any, model_override: Optional[str]
    ) -> Optional[str]:
        """Resolves the model identity used by cost-failure diagnostics."""
        if model_override:
            return str(model_override)
        model_id = getattr(completion_response, "model", None)
        if model_id:
            return str(model_id)
        config_model = self._config_service.get_setting("llm.model")
        return str(config_model) if config_model else None

    def _extract_usage_value(
        self, completion_response: Any, attr: str
    ) -> Optional[int]:
        """Defensively extracts an integer field from the usage object."""
        usage = getattr(completion_response, "usage", None)
        if usage is None:
            return None
        value = getattr(usage, attr, None)
        return value if isinstance(value, int) else None

    def _extract_detail_value(
        self, completion_response: Any, details_attr: str, value_attr: str
    ) -> Optional[int]:
        """Defensively extracts a nested token detail from the usage object."""
        usage = getattr(completion_response, "usage", None)
        if usage is None:
            return None
        details = getattr(usage, details_attr, None)
        if details is None:
            return None
        value = getattr(details, value_attr, None)
        return value if isinstance(value, int) else None

    def validate_config(self, include_remote: bool = False) -> List[str]:
        """
        Validates the LLM configuration for common errors.
        - Delegates key-requiredness to litellm (provider-aware), so keyless
          local models validate cleanly while cloud models still surface a
          friendly missing-key error.
        - Checks for missing provider-specific environment variables.
        - Optionally performs a lightweight remote connectivity check.
        """
        model = self._config_service.get_setting("llm.model")
        if not model:
            return ["'llm.model' is not configured."]

        api_key = self._config_service.get_setting("llm.api_key")
        is_api_key_provided = isinstance(api_key, str) and bool(api_key.strip())

        # Provider-aware check: litellm knows what each model actually requires,
        # so keyless local models (lm_studio/vllm/ollama) validate cleanly while
        # cloud models still surface a friendly missing-key error. Only
        # *_API_KEY requirements are hard errors; any other reported requirement
        # (e.g. OLLAMA_API_BASE, a base URL defaulting to localhost) is advisory.
        litellm = self._get_litellm()
        errors: List[str] = []
        validation_result = litellm.validate_environment(model=model)
        missing_keys = validation_result.get("missing_keys", [])

        for key in missing_keys:
            if "_API_KEY" not in key:
                continue
            if is_api_key_provided:
                continue
            errors.append(
                f"'llm.api_key' is empty: {key} is required for model "
                f"'{model}'. Set TEDDY_LLM_API_KEY in .teddy/.env "
                "(or your shell environment)."
            )

        # 3. Optional Remote Check: Verify key validity/expiration
        if not errors and include_remote and is_api_key_provided:
            from concurrent.futures import TimeoutError

            executor = self._get_executor()
            future = executor.submit(
                litellm.check_valid_key, model=model, api_key=api_key
            )
            try:
                is_valid = future.result(timeout=10.0)
                if not is_valid:
                    errors.append(
                        "The API key appears to be invalid, expired, or deactivated."
                    )
            except TimeoutError:
                errors.append(
                    "The remote connectivity check timed out after 10 seconds."
                )
            except Exception as e:
                errors.append(f"Remote connectivity check failed: {str(e)}")

        return errors

    def get_context_window(self, model: Optional[str] = None) -> int:
        """
        Returns the maximum context window size (tokens) for the specified model.
        """
        litellm = self._get_litellm()

        resolved_model = model or self._config_service.get_setting("llm.model")
        if not resolved_model:
            return 0

        # Pre-emptive Hydration: If the model is unknown and we have a hydrator, try to fetch it now.
        # This ensures that Turn 1 telemetry can display correct info even before the first AI call.
        if str(resolved_model) not in litellm.model_cost and self._hydrator:
            candidates = {str(resolved_model)}
            self._hydrate_all_candidates(candidates)

        model_info = litellm.model_cost.get(str(resolved_model), {})

        # Heuristic: max_input_tokens is specific to the context window.
        # max_tokens often refers to the output limit but is used as a fallback in litellm metadata.
        return int(
            model_info.get("max_input_tokens") or model_info.get("max_tokens") or 0
        )

    def validate_model(self, model: Optional[str]) -> bool:
        """Check if a model exists in LiteLLM's registry.

        Returns True if the model is known or if no override is given
        (the config model will be used instead of an override).
        """
        if model is None:
            return True  # No override; config model will be used
        if not model:
            return False
        litellm = self._get_litellm()
        clean = model.removeprefix("openrouter/")
        if clean in litellm.model_cost:
            return True
        if model in litellm.model_cost:
            return True
        return False

    def supports_pricing(self, model: Optional[str] = None) -> bool:
        """
        Returns True if the model has known pricing metadata in the registry.
        """
        litellm = self._get_litellm()
        resolved_model = model or self._config_service.get_setting("llm.model")
        if not resolved_model:
            return False

        model_cost = litellm.model_cost
        if not isinstance(model_cost, dict):
            # Defensive: a non-dict registry (e.g. a bare test double) exposes
            # no pricing metadata; treat it as unpriced rather than crashing.
            return False
        model_info = model_cost.get(str(resolved_model), {})
        # input_cost_per_token is the primary indicator of pricing metadata
        return "input_cost_per_token" in model_info

    def _handle_hydration_retry(
        self, error: Exception, messages: List[Dict[str, str]], params: Dict[str, Any]
    ) -> Optional[Any]:
        """Internal helper to detect NotFoundError and retry once with hydrated metadata."""
        litellm = self._get_litellm()

        if not (self._is_not_found_error(error) and self._hydrator):
            return None

        # 1. Identify all candidate model IDs for hydration
        candidates = self._identify_hydration_candidates(error, params)
        if not candidates:
            return None

        # 2. Hydrate all candidates using the first successful metadata found
        if not self._hydrate_all_candidates(candidates):
            return None

        # 3. Retry once
        return litellm.completion(messages=messages, **params)

    def _hydrate_all_candidates(self, candidates: set[str]) -> bool:
        """
        Internal helper to fetch metadata for any candidate and broadcast it to all.
        Returns True if any metadata was found and injected.
        """
        if not self._hydrator:
            return False

        litellm = self._get_litellm()
        shared_metadata = None
        for m_id in candidates:
            shared_metadata = self._hydrator.get_metadata(m_id)
            if shared_metadata:
                break

        if not shared_metadata:
            return False

        for m_id in candidates:
            # Update LiteLLM's internal registry for all candidate IDs
            # Ensure pricing values are floats to prevent `float + str` crashes
            pricing = shared_metadata.get("pricing", {})
            safe_pricing = {}
            for key, val in pricing.items():
                try:
                    safe_pricing[key] = float(val)
                except (ValueError, TypeError):
                    safe_pricing[key] = 0.0
            litellm.model_cost[m_id] = {
                "max_input_tokens": shared_metadata.get("context_window", 0),
                **safe_pricing,
            }
        return True

    def _is_not_found_error(self, error: Exception) -> bool:
        """Robustly checks if the error is a LiteLLM NotFoundError."""
        litellm = self._get_litellm()

        if type(error).__name__ == "NotFoundError":
            return True

        if hasattr(litellm, "NotFoundError"):
            not_found_cls = getattr(litellm, "NotFoundError")
            return isinstance(not_found_cls, type) and isinstance(error, not_found_cls)

        return False

    def _identify_hydration_candidates(
        self, error: Exception, params: Dict[str, Any]
    ) -> set[str]:
        """Extracts requested and resolved model IDs from params and error message."""
        import re

        candidates = set()
        requested_model = params.get("model")
        if requested_model:
            candidates.add(str(requested_model))

        # Parse actual model from error message (e.g. "model=deepseek/deepseek-v4...")
        match = re.search(r"model=([^,\s]+)", str(error))
        if match:
            candidates.add(match.group(1))

        return candidates
