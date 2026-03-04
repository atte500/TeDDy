**Status:** Implemented
**Introduced in:** [Slice 10: Foundation (Security, Config, LLM Client)](/docs/project/slices/10-foundation-security-config-llm.md)

## 1. Purpose / Responsibility

The `LiteLLMAdapter` is responsible for interacting with various Large Language Models using the `litellm` library. It provides a concrete implementation for the `ILlmClient` port.

## 2. Ports

-   **Type:** Outbound Adapter
-   **Implements:** `ILlmClient`
-   **Uses:** `IConfigService` (to retrieve API keys and other model settings).

## 3. Implementation Details / Logic

-   This adapter will be initialized with a dependency on `IConfigService`.
-   Before making an API call, it will use the `IConfigService` to retrieve the necessary credentials (e.g., `OPENAI_API_KEY`) and set them as environment variables for `litellm` to consume.
-   It will wrap all calls to `litellm.completion` in a `try...except` block to catch specific `litellm` exceptions (e.g., `AuthenticationError`, `RateLimitError`) and re-raise them as a generic `LlmApiError` to conform to the port's contract.
-   The successful spike script that validated the core functionality can be found at `spikes/plumbing/verify_litellm_integration.py`.

## 4. Data Contracts / Methods

This adapter implements the methods defined in the `ILlmClient` port contract. See `docs/architecture/core/ports/outbound/llm_client.md`.
