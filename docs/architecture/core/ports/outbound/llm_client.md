**Status:** Implemented
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

### `get_completion(self, model: str, messages: List[Dict[str, str]], **kwargs) -> Any`

-   **Description:** Sends a request to an LLM and returns the raw response object (e.g., LiteLLM ModelResponse).
-   **Preconditions:**
    -   `model` must be a non-empty string.
    -   `messages` must follow the chat completion format.
-   **Postconditions:**
    -   Returns the provider-specific completion object.
-   **Exception/Error States:**
    -   `LlmApiError`: Raised for API or communication failures.

### `get_token_count(self, model: str, messages: List[Dict[str, str]]) -> int`
- **Description:** Calculates the number of tokens in the payload for a specific model (Pre-flight).

### `get_completion_cost(self, completion_response: Any) -> float`
- **Description:** Calculates the precise USD cost of a completion response (Post-flight).
