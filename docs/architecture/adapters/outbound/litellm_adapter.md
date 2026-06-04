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

- **Transient Network Failures:** Handled via a stateful retry loop. The number of attempts is determined by `llm.max_retries` (default: 3).
- **SSL Handshake Errors:** Specific errors like `SSLV3_ALERT_BAD_RECORD_MAC` trigger retries.
- **API Timeouts:** OpenRouter or provider timeouts trigger retries.
- **Permanent Configuration Errors:** (Invalid API key) raise `ConfigurationError` immediately.

## 4. Implementation Details / Logic

-   **Stateful Retries:** `get_completion` implements a retry loop for specific transient exceptions. Each attempt is logged to the debug stream.
-   **Lazy Initialization:** To maintain CLI responsiveness (initialization < 500ms), both the `litellm` library and the `ThreadPoolExecutor` are loaded lazily and protected by an internal lock.
-   **Logging Suppression:** The adapter performs a double-pass silencing protocol (once before and once after `litellm` import). It sets `LITELLM_LOG=CRITICAL` and configures the `LiteLLM` logger to `CRITICAL` level to suppress noisy `botocore` warnings.
-   **OpenRouter Resilience:** Implements a trigger-and-retry mechanism. Upon receiving a `NotFoundError`, the adapter extracts the model ID from the error message and uses the hydrator to inject metadata (context window, pricing) into `litellm.model_cost` before retrying.
-   **Remote Check Timeouts:** All remote connectivity and configuration checks (e.g., `litellm.check_valid_key`) are capped at a 10.0-second timeout via a background executor to accommodate library initialization and network latency.
-   **Ultra-Lazy Validation:** Local configuration checks (existence of API key and model) are performed before importing the heavy `litellm` library, ensuring sub-second response times for common errors.
-   **Error Handling:** Wraps all `litellm` operations to re-raise specific failures as `LlmApiError` or `ConfigurationError`, ensuring transparent CLI feedback.
-   **Provider Resolution:** After each successful `litellm.completion()`, the actual downstream provider that served the request is available in `response._hidden_params["provider"]` (e.g., `"deepseek"`, `"together"`, `"openai"`). This value is extracted by `PromptManager.update_meta` for display in the CLI telemetry. The adapter does NOT special-case the `llm.provider` config value — the entire `llm` config section passes through transparently to litellm via `params.update(llm_config)`, allowing any litellm-supported parameter (including OpenRouter's `extra_body.providers.order`) to be set directly in `config.yaml`.
-   **`:nitro` / `:floor` Shortcuts:** The `openrouter_hydrator` strips `:nitro` and `:floor` suffixes from model names to derive the base model ID for metadata fetching. These suffixes are TeDDy-specific conventions for selecting performance/cost tiers and are transparent to litellm.

## 4. Data Contracts / Methods

This adapter implements the methods defined in the `ILlmClient` port contract:

### `get_completion(model, messages, **kwargs) -> Any`
-   **Description:** Fetches a chat completion from the configured LLM.

### `get_token_count(model, messages) -> int`
-   **Description:** Uses `litellm.token_counter` to provide a pre-flight token estimate.

### `get_completion_cost(completion_response) -> float`
-   **Description:** Uses `litellm.completion_cost` to calculate the precise USD cost of a response.
