# Component Design: LiteLLMAdapter
- **Status:** Implemented
- **Source:** [`src/teddy_executor/adapters/outbound/litellm_adapter.py`](/src/teddy_executor/adapters/outbound/litellm_adapter.py)

## Purpose
Implements the `ILlmClient` outbound port using the `litellm` library. It provides multi-provider completions, token counts, context-window lookups, and cost telemetry, with lazy initialization, config validation, and bounded retries.

## Consumers
- [`PlanningService`](../../core/services/planning_service.md): Requests plan completions and computes the context-window and token budgets.
- [Composition Root](/src/teddy_executor/container.py): Registers `LiteLLMAdapter` against `ILlmClient`.

## Dependencies
- [`IConfigService`](../../core/ports/outbound/config_service.md): Reads the `llm.*` settings and the API key.
- **`IOpenRouterHydrator`** (`teddy_executor.adapters.outbound.litellm_adapter`): An internal adapter-layer protocol that fetches live model metadata from OpenRouter.
- **`ITimeService`** (`teddy_executor.core.ports.outbound.time_service`): Injectable; supplies the retry backoff sleep. The composition root injects the shared `SystemTimeAdapter`, so a container-resolved client sleeps through the seam. A direct construction without it falls back to the real `time.sleep`.
- **`litellm`** (external): Imported lazily and silenced before and after import.
- **`tiktoken`** (external): Imported lazily for the text token count.

## Class Invariants
- `lazy_initialization`: The `litellm` import and the `ThreadPoolExecutor` are created lazily under `_init_lock`.
- `validated_flag`: `_validated` is guarded by `_init_lock`, so concurrent first calls validate exactly once.
- `auth_not_retried`: Authentication errors are never retried; they surface immediately as `ConfigurationError`.
- `error_translation`: Provider failures surface as `LlmApiError` or `ConfigurationError`, never as a raw provider exception.
- `cost_never_raises`: `get_completion_cost` returns `0.0` on any failure and never raises.
- `reported_cost_precedence`: `get_completion_cost` prefers the cost the response itself reports before any registry recompute, because it reflects the vendor that actually served the request. On an OpenRouter BYOK response the real spend is `usage.cost_details.upstream_inference_cost`, which outranks the waived `usage.cost` fee.
- `recorded_cost_signal`: A real price (reported, or a successful recompute including a free-model `0.0`) sets `_teddy_cost_recorded=True` on the response; the recompute-failure fallback `0.0` is left unmarked.

## Inbound Ports
None — this is an outbound (driven) adapter.

## Outbound Ports
- **`ILlmClient`**: The driven contract implemented by this adapter. See the [ILlmClient design](../../core/ports/outbound/llm_client.md).
- **`IOpenRouterHydrator`**: An internal port consumed for OpenRouter metadata hydration.

## Data Contracts
- **`messages`** (`List[Dict[str, str]]`): The chat-completion payload.
- **`llm.*` config keys:** The entire `llm` section passes through to `litellm.completion()`. The adapter reads `llm.model`, `llm.api_key`, `llm.max_retries` (default 3), and `llm.timeout` (default 300 seconds).
- **Model registry cache:** JSON at `.teddy/.model_registry_cache.json`, payload `{"version": 1, "fetched_at_epoch": <int>, "models": [...]}`, with a 7-day TTL.

## Operations

### `get_completion(messages, model=None, **kwargs) -> Any`
- **Preconditions:** The config carries a model and, when the provider requires one, an API key.
- **Postconditions:** Returns the provider completion object. The first call validates the config once; later calls skip validation.
- **Exceptions:** `ConfigurationError` for a missing model, a missing required key, or an auth failure; `LlmApiError` after retry exhaustion.

### `get_token_count(messages, model=None) -> int`
- **Postconditions:** Returns the token count from `litellm.token_counter`.

### `get_text_token_count(text, model=None) -> int`
- **Postconditions:** Returns the token count of a raw string through the cached `tiktoken` encoding. Returns `0` for empty text.

### `get_completion_cost(completion_response, model_override=None) -> float`
- **Postconditions:** Returns the USD cost, reading the response before any registry recompute in this order: a positive `usage.cost_details.upstream_inference_cost` (OpenRouter BYOK spend) plus any reported fee; then `_hidden_params["response_cost"]`; then the OpenRouter `additional_headers["llm_provider-x-litellm-response-cost"]` header. A non-dict holder, an absent/`None` value, or a non-finite value falls through to the next source. When no reported cost is present it recomputes via `litellm.completion_cost`. On a real price (reported, upstream, or a successful recompute, including a free-model `0.0`) it sets `_teddy_cost_recorded=True` on the response so the display can trust the figure; the recompute-failure fallback `0.0` is left unmarked.
- **Postconditions:** On failure it logs with tiered severity (WARNING for a priced-model anomaly, DEBUG for an unpriced-model miss) and returns `0.0`.

### `validate_config(include_remote=False) -> List[str]`
- **Postconditions:** Returns configuration error messages, where an empty list means valid.
- **Postconditions:** Key-requiredness delegates to `litellm.validate_environment`, so keyless local models validate cleanly. A non-key requirement stays advisory.
- **Postconditions:** When no earlier error exists and `llm.api_base` is unset, provider resolution runs under captured stdout. An unresolvable model then returns a paste-ready error naming `llm.model`.
- **Postconditions:** When `include_remote` is `True`, a connectivity check runs with a 10-second timeout.

### `get_context_window(model=None) -> int`
- **Postconditions:** Returns the model context window, or `0` when unknown. It pre-emptively hydrates an unknown model so first-turn telemetry shows real values.

### `validate_model(model=None) -> bool`
- **Postconditions:** Returns `True` when the model is known to `litellm` or when no override is given. Returns `False` for an unknown override.

### `supports_pricing(model=None) -> bool`
- **Postconditions:** Returns `True` when the model's registry entry carries `input_cost_per_token`. A non-dict registry is treated as unpriced.

### Cost-failure diagnostics identity
`_resolve_cost_model` prefers `completion_response.model` — the identity the registry recompute prices against — over the configured `model_override` for the anomaly summary and the WARNING-vs-DEBUG tier. A routing override (e.g. `openrouter/foo`) absent from the registry therefore never downgrades a real priced-model failure to DEBUG, and the logged identity matches the model actually priced.

### BYOK cost accounting
OpenRouter reports two figures on a response. `usage.cost` is what OpenRouter charges for the request; under BYOK that is a fee of 5% of list price, waived while the monthly free allowance lasts, so it is frequently `0.0`. `usage.cost_details.upstream_inference_cost` is what the user's own provider actually billed. litellm mirrors `usage.cost` into `_hidden_params` but preserves `usage.cost_details` verbatim on the response, so the adapter reads the upstream field directly: a positive value wins, with any reported fee added on top. OpenRouter reports `0` or `null` for the upstream field on non-BYOK requests, so those keep the fee as their authoritative figure.

### Retry and authentication handling
The retry loop attempts `llm.max_retries` times with exponential backoff (`0.5 * 2**attempt`). `_is_auth_error` detects an auth failure by message hint or by the `litellm.AuthenticationError` type, so a wrong or expired key fails on the first attempt with no backoff.

### OpenRouter metadata hydration
`OpenRouterMetadataHydrator` implements `IOpenRouterHydrator`. It fetches the OpenRouter catalog for models absent from `litellm.model_cost`, caches the catalog at `.teddy/.model_registry_cache.json` with a 7-day TTL, writes atomically, and treats a missing or corrupt cache as empty. On a `NotFoundError`, the adapter extracts the model ID, hydrates `litellm.model_cost`, and retries once. The `:nitro` and `:floor` OpenRouter routing suffixes are stripped when deriving the base model ID.
