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

## Inbound Ports
None — this is an outbound (driven) port.

## Outbound Ports
- **`ILlmClient`**: The driven contract consumed by core services and implemented by the `LiteLLMAdapter`.

## Data Contracts
- **`LlmApiError`** (`Exception`): Raised for any failure during an LLM API call.
- **`messages`**: A list of `{"role": str, "content": str}` dictionaries in chat-completion format.

## Operations

### `get_completion(messages, model=None, **kwargs) -> Any`
- **Preconditions:** `messages` follows the chat-completion format.
- **Postconditions:** Returns the provider completion object.
- **Exceptions:** `LlmApiError` when the API call fails.

### `get_token_count(messages, model=None) -> int`
- **Preconditions:** `messages` follows the chat-completion format.
- **Postconditions:** Returns the token count of the payload.

### `get_text_token_count(text, model=None) -> int`
- **Preconditions:** None.
- **Postconditions:** Returns the token count of a raw string.

### `get_completion_cost(completion_response, model_override=None) -> float`
- **Preconditions:** `completion_response` is a response from `get_completion`.
- **Postconditions:** Returns the USD cost of the completion.

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
