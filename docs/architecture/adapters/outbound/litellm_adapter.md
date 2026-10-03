**Status:** Implemented

## 1. Purpose / Responsibility

The `LiteLLMAdapter` is responsible for interacting with various Large Language Models using the `litellm` library. It provides a concrete implementation for the `ILlmClient` port.

## 2. Ports

-   **Type:** Outbound Adapter
-   **Implements:** `ILlmClient`
-   **Uses:**
    - `IConfigService`: For retrieving model settings and API keys.
    - `IOpenRouterHydrator` (Internal): For dynamic metadata fetching from OpenRouter.

## 3. Failure Modes

- **Configuration Errors (Invalid API Key / Missing Model):** Detected at startup by `validate_config()` and raised as `ConfigurationError` immediately — no litellm call is made. This check runs at two levels:
  - **Caller-Level (Primary Gate):** `planning_service.py` and `session_cli_handlers.py` call `validate_config()` before `get_completion()`.
  - **Adapter-Level (Defense-in-Depth):** A `_validated` flag (protected by `_init_lock` for thread safety) ensures that even if `get_completion()` is called directly without prior validation, the config is checked on the first invocation.
- **Transient Failures (Network, Server Errors, Timeouts):** After config validation has passed, ALL exceptions during `litellm.completion()` are treated as transient and retried with exponential backoff (0.5s * 2^attempt). Max attempts is determined by `llm.max_retries` (default: 3). This includes:
  - SSL handshake errors (e.g., `SSLV3_ALERT_BAD_RECORD_MAC`)
  - API timeouts (OpenRouter / provider)
  - Generic network errors (e.g., `Connection refused`)
  - Server errors (e.g., `500 Internal Server Error`)
- **Permanent Errors (After Retry Exhaustion):** If all retry attempts fail, `LlmApiError` is raised preserving the original exception message. Additionally, if the error indicates an invalid API key (`API_KEY_INVALID`, `invalid_api_key`), a `ConfigurationError` is raised from the final exception to provide a clear error message.
- **Timeout Passthrough:** The optional `timeout` key under the `llm` config section is passed directly to `litellm.completion()` via `params.update(llm_config)`. If not configured, defaults to 300 seconds (5 minutes). No timeout or `timeout: null` uses litellm's own default (no forced timeout).

## 4. Implementation Details / Logic

-   **Lazy Validation Guard:** After `__init__`, `_validated` is set to `False`. On first `get_completion()` call, the adapter checks this flag under the `_init_lock` (thread-safe). If not validated, it calls `validate_config()`. If errors are returned, `ConfigurationError` is raised immediately with no litellm call. On success, `_validated` is set to `True` and subsequent calls skip validation entirely. This ensures defense-in-depth even if `get_completion()` is called directly without prior validation by callers.
-   **Retry-All-Errors Logic:** Once config validation has passed (either via the internal guard or by external callers), `_should_retry_completion()` retries on ALL exceptions — not just SSL/Timeout. The method checks `attempt < max_attempts - 1` and applies exponential backoff (`0.5 * 2^attempt` seconds). This simplifies the logic significantly: after validation, any error is assumed transient.
-   **Timeout Passthrough:** The `timeout` key under the `llm` config section (with default `300` in `config.yaml`) is passed through automatically by `params.update(llm_config)` in `_prepare_completion_params()`. No special handling is needed — the layering mechanism handles it.
-   **Thread Safety:** All lazy initialization (litellm import, encoding cache, validation flag) uses the same `_init_lock` pattern. Five concurrent calls to `get_completion()` have been validated to all succeed with validation running exactly once.
-   **Stateful Retries:** `get_completion` implements a retry loop for all exceptions after validation passes. Each attempt is logged to the debug stream.
-   **Lazy Initialization:** To maintain CLI responsiveness (initialization < 500ms), both the `litellm` library and the `ThreadPoolExecutor` are loaded lazily and protected by an internal lock.
-   **Logging Suppression:** The adapter performs a double-pass silencing protocol (once before and once after `litellm` import). It sets `LITELLM_LOG=CRITICAL` and configures the `LiteLLM` logger to `CRITICAL` level to suppress noisy `botocore` warnings.
-   **OpenRouter Resilience:** Implements a trigger-and-retry mechanism. Upon receiving a `NotFoundError`, the adapter extracts the model ID from the error message and uses the hydrator to inject metadata (context window, pricing) into `litellm.model_cost` before retrying.
-   **Remote Check Timeouts:** All remote connectivity and configuration checks (e.g., `litellm.check_valid_key`) are capped at a 10.0-second timeout via a background executor to accommodate library initialization and network latency.
-   **Ultra-Lazy Validation:** Local configuration checks (existence of API key and model) are performed before importing the heavy `litellm` library, ensuring sub-second response times for common errors.
-   **Error Handling:** Wraps all `litellm` operations to re-raise specific failures as `LlmApiError` or `ConfigurationError`, ensuring transparent CLI feedback.
-   **Cost-Failure Transparency (Slice 00-24):** `get_completion_cost` never raises — a cost-computation failure preserves the `0.0` return contract (cost is non-critical-path telemetry on an already-successful completion). Before each `return 0.0` it calls `_log_cost_failure(error, completion_response, model_override)` with `exc_info=True`, tiered by severity: `logger.warning` when the resolved model HAS pricing metadata (`input_cost_per_token` present in its `litellm.model_cost` entry) yet `completion_cost` raised (an anomaly — real spend silently lost), `logger.debug` when the model is unpriced (an expected miss, mirroring the TUI `$???` placeholder). Model identity is resolved `model_override` → `completion_response.model` → config `llm.model`; the usage summary is extracted defensively (prompt/completion tokens plus optional `cached_tokens`/`reasoning_tokens`). `supports_pricing` is hardened against a non-dict `litellm.model_cost` shape (treated as unpriced).
-   **Provider Resolution:** After each successful `litellm.completion()`, the actual downstream provider that served the request is available in `response._hidden_params["provider"]` (e.g., `"deepseek"`, `"together"`, `"openai"`). This value is extracted by `PromptManager.update_meta` for display in the CLI telemetry. The adapter does NOT special-case the `llm.provider` config value — the entire `llm` config section passes through transparently to litellm via `params.update(llm_config)`, allowing any litellm-supported parameter (including OpenRouter's `extra_body.providers.order`) to be set directly in `config.yaml`.
-   **`:nitro` / `:floor` Shortcuts:** The `openrouter_hydrator` strips `:nitro` and `:floor` suffixes from model names to derive the base model ID for metadata fetching. These suffixes are TeDDy-specific conventions for selecting performance/cost tiers and are transparent to litellm.

## 4. Data Contracts / Methods

This adapter implements the methods defined in the `ILlmClient` port contract:

### `get_completion(model, messages, **kwargs) -> Any`
-   **Description:** Fetches a chat completion from the configured LLM.

### `get_token_count(model, messages) -> int`
-   **Description:** Uses `litellm.token_counter` to provide a pre-flight token estimate.

### `get_completion_cost(completion_response) -> float`
-   **Description:** Uses `litellm.completion_cost` to calculate the precise USD cost of a response. On any cost-computation failure it logs at a tiered level (WARNING for a priced-model anomaly, DEBUG for an unpriced-model miss) and returns `0.0` — see Cost-Failure Transparency above.

## 5. OpenRouterMetadataHydrator: Persistent Registry Cache (Slice 00-20)

`OpenRouterMetadataHydrator` (implements `IOpenRouterHydrator`) fetches the OpenRouter catalog for models not present in `litellm.model_cost`. It gains a **persistent cache**:

- **Storage:** JSON at `.teddy/.model_registry_cache.json`; payload `{"version": 1, "fetched_at_epoch": <int>, "models": [...]}`. The path is covered by the shipped `.teddy/.gitignore` template (bare `*` rule).
- **TTL:** 7 days default (configurable via `IConfigService`); `now - fetched_at_epoch >= ttl` → expired → one refetch on the next hydration, then rewrite.
- **Failure handling:** missing/corrupt cache → treated as empty → refetch; never serve wrong metadata.
- **Cache-pricing broadcast (Slice 00-24):** `_find_model` maps the catalog's per-token cache rates `input_cache_read`/`input_cache_write` to litellm's `cache_read_input_token_cost`/`cache_creation_input_token_cost`, float-parsed inside the existing `ValueError`/`TypeError` guard and emitted ONLY when present AND parsed `> 0` (a `0.0` rate is equivalent to the cached-tokens-billed-at-$0 defect and is therefore omitted; absent keys ⇒ keys omitted ⇒ prior behaviour). Without this, hydrated models lacked cache rates in `litellm.model_cost`, so cached tokens billed at $0 and Anthropic-shaped usage could yield a negative prompt cost.
- **Writes:** atomic (`<name>.tmp` + `os.replace`).
- **Injection:** the cache loader/path is constructor-injected at the `registries/infrastructure.py` factory (the hydrator is registered with singleton scope). Per-instance in-memory memoization is unchanged.
- Pre-emptive hydration (via `get_context_window` in `PlanningService.generate_plan`) is retained so first-turn telemetry shows real values.
