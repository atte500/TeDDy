**Status:** Implemented
**Introduced in:** [Slice 10: Foundation (Security, Config, LLM Client)](/docs/project/slices/10-foundation-security-config-llm.md)

## 1. Purpose / Responsibility

The `LiteLLMAdapter` is responsible for interacting with various Large Language Models using the `litellm` library. It provides a concrete implementation for the `ILlmClient` port.

## 2. Ports

-   **Type:** Outbound Adapter
-   **Implements:** `ILlmClient`
-   **Uses:** `IConfigService` (to retrieve API keys and other model settings).

## 3. Implementation Details / Logic

-   **Lazy Loading:** To maintain CLI responsiveness, the `litellm` library is imported lazily within the methods where it is used. This ensures initialization remains under the 500ms threshold.
-   **Logging Suppression:** The adapter explicitly disables `litellm`'s internal verbose logging (`litellm.set_verbose = False`) and suppresses debug info to keep the CLI output clean. It configures the `LiteLLM` logger to `WARNING` level.
-   **Environment Configuration:** Before making an API call, it uses the `IConfigService` to retrieve credentials and set them as environment variables for `litellm` to consume.
-   **Error Handling:** Wraps all calls to `litellm.completion` to catch specific exceptions (e.g., `AuthenticationError`, `RateLimitError`) and re-raise them as `LlmApiError`.

## 4. Data Contracts / Methods

This adapter implements the methods defined in the `ILlmClient` port contract:

### `get_completion(model, messages, **kwargs) -> Any`
-   **Description:** Fetches a chat completion from the configured LLM.

### `get_token_count(model, messages) -> int`
-   **Description:** Uses `litellm.token_counter` to provide a pre-flight token estimate.

### `get_completion_cost(completion_response) -> float`
-   **Description:** Uses `litellm.completion_cost` to calculate the precise USD cost of a response.
