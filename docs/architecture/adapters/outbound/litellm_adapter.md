**Status:** Implemented

## 1. Purpose / Responsibility

The `LiteLLMAdapter` is responsible for interacting with various Large Language Models using the `litellm` library. It provides a concrete implementation for the `ILlmClient` port.

## 2. Ports

-   **Type:** Outbound Adapter
-   **Implements:** `ILlmClient`
-   **Uses:**
    - `IConfigService`: For retrieving model settings and API keys.
    - `IOpenRouterHydrator` (Internal): For dynamic metadata fetching from OpenRouter.

## 3. Implementation Details / Logic

-   **Lazy Initialization:** To maintain CLI responsiveness (initialization < 500ms), both the `litellm` library and the `ThreadPoolExecutor` are loaded lazily and protected by an internal lock.
-   **Logging Suppression:** The adapter performs a double-pass silencing protocol (once before and once after `litellm` import). It sets `LITELLM_LOG=CRITICAL` and configures the `LiteLLM` logger to `CRITICAL` level to suppress noisy `botocore` warnings.
-   **OpenRouter Resilience:** Implements a trigger-and-retry mechanism. Upon receiving a `NotFoundError`, the adapter extracts the model ID from the error message and uses the hydrator to inject metadata (context window, pricing) into `litellm.model_cost` before retrying.
-   **Remote Check Timeouts:** All remote connectivity and configuration checks (e.g., `litellm.check_valid_key`) are capped at a 2.0-second timeout via a background executor.
-   **Error Handling:** Wraps all `litellm` operations to re-raise specific failures as `LlmApiError` or `ConfigurationError`, ensuring transparent CLI feedback.

## 4. Data Contracts / Methods

This adapter implements the methods defined in the `ILlmClient` port contract:

### `get_completion(model, messages, **kwargs) -> Any`
-   **Description:** Fetches a chat completion from the configured LLM.

### `get_token_count(model, messages) -> int`
-   **Description:** Uses `litellm.token_counter` to provide a pre-flight token estimate.

### `get_completion_cost(completion_response) -> float`
-   **Description:** Uses `litellm.completion_cost` to calculate the precise USD cost of a response.
