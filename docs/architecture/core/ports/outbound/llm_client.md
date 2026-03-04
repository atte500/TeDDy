**Status:** Planned
**Introduced in:** [Slice 10: Foundation (Security, Config, LLM Client)](/docs/project/slices/10-foundation-security-config-llm.md)

## 1. Purpose / Responsibility

The `ILlmClient` port defines a generic interface for communicating with a Large Language Model (LLM). It abstracts the specifics of any particular LLM provider (e.g., OpenAI, Anthropic) or library (e.g., `litellm`) from the core application.

## 2. Ports

-   **Type:** Outbound Port
-   **Used by:** Any core service that needs to interact with an LLM.
-   **Implemented by:** Adapters like `LiteLLMAdapter`.

## 3. Implementation Details / Logic

This is an interface and contains no implementation logic.

## 4. Data Contracts / Methods

### `get_completion(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str`

-   **Description:** Sends a request to an LLM and returns the completed text response.
-   **Preconditions:**
    -   `model` must be a non-empty string identifying the target model.
    -   `messages` must be a list of dictionaries, each with "role" and "content" keys, conforming to the standard chat completion format.
-   **Postconditions:**
    -   Returns the string content of the LLM's response upon success.
-   **Exception/Error States:**
    -   `LlmApiError`: Raised for any failures during the API call (e.g., authentication failure, network error, rate limiting). The underlying exception will be wrapped.
