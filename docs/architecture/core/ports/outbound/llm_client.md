# Component Design: ILlmClient
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/ports/outbound/llm_client.py`](/src/teddy_executor/core/ports/outbound/llm_client.py)

## Purpose
Defines the outbound port for communicating with a Large Language Model. It abstracts the provider and library so core services request completions, token counts, and costs without coupling to LiteLLM.

## Consumers
- [`PlanningService`](../../services/planning_service.md): Requests plan completions and computes context-window and token budgets.

## Dependencies
None — this port declares no injected dependencies.

## Class Invariants
- `abstract_base_class`: The port is an `ABC`; implementations override every abstract operation.
- `error_translation`: Every provider failure surfaces as `LlmApiError`, never a provider-specific exception.
- `usage_zero_fill`: `get_token_usage` is concrete and returns a zeroed `TokenUsage`, so a client that cannot observe provider accounting inherits that default instead of reporting a guess.

## Inbound Ports
None — this is an outbound (driven) port.

## Outbound Ports
- **`ILlmClient`**: The driven contract consumed by core services and implemented by the `LiteLLMAdapter`.

## Data Contracts
- **`LlmApiError`** (`Exception`): Raised for any failure during an LLM API call.
- **`ConfigurationError`** (`teddy_executor.core.domain.models.exceptions`): Raised for a rejected configuration value, including a truthy `stream` in the merged parameters.
- **`messages`**: A list of `{"role": str, "content": str}` dictionaries in chat-completion format.
- **`llm_overrides`**: An optional `Mapping[str, Any]` carrying the active persona's `llm` settings; `None` by default so every existing caller and fake stays valid.
- **`TokenUsage`** (`teddy_executor.core.domain.models.token_usage`): The frozen DTO carrying the provider's `prompt_tokens` and `cached_tokens`, both `int` and both `0` when the provider reports nothing. Its `prompt_tokens` is the provider's own count, never the pre-call `get_token_count` estimate.

## Operations

### `get_completion(messages, model=None, llm_overrides=None, **kwargs) -> Any`
- **Preconditions:** `messages` follows the chat-completion format. The merged parameters carry no truthy `stream`, because the port returns one complete, non-streamed response.
- **Postconditions:** Returns the provider completion object. `llm_overrides` is an optional per-persona overlay merged over the global `llm` block, with the per-call `model` still applied last.
- **Exceptions:**
  - `ConfigurationError`: A rejected configuration value, including a truthy `stream` in the merged parameters.
  - `LlmApiError`: Remote provider failure, rate limit, timeout, or malformed response.

### `get_token_count(messages, model=None) -> int`
- **Preconditions:** `messages` follows the chat-completion format.
- **Postconditions:** Returns the token count of the payload.

### `get_text_token_count(text, model=None) -> int`
- **Preconditions:** None.
- **Postconditions:** Returns the token count of a raw string.

### `get_token_usage(completion_response) -> TokenUsage`
- **Preconditions:** `completion_response` is a response from `get_completion`; the port keeps it opaque, so the DTO is the only shape crossing the boundary.
- **Postconditions:** Returns the provider-reported usage, with any field the provider omits reading as `0`. A client that inherits the concrete default returns a zeroed `TokenUsage`.

### `get_completion_cost(completion_response, model_override=None) -> float`
- **Preconditions:** `completion_response` is a response from `get_completion`.
- **Postconditions:** Returns the USD cost of the completion. An implementation may prefer a cost the provider reported on the response over a local registry recompute, because the reported value reflects the vendor that actually served the request.

### `validate_config(include_remote=False) -> List[str]`
- **Preconditions:** None.
- **Postconditions:** Returns configuration error messages; an empty list means valid.
- **Design Note:** When `include_remote` is `True`, performs a lightweight connectivity check.

### `get_context_window(model=None) -> int`
- **Preconditions:** None.
- **Postconditions:** Returns the model context window in tokens, or `0` when unknown.

### `supports_pricing(model=None) -> bool`
- **Preconditions:** None.
- **Postconditions:** Returns `True` when pricing metadata exists, even at `$0.00`.
