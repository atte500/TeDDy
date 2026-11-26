# Component Design: TokenUsage
- **Status:** Implemented
- **Classification:** Core Domain
- **Source:** [`src/teddy_executor/core/domain/models/token_usage.py`](/src/teddy_executor/core/domain/models/token_usage.py)

## Purpose
A frozen value object carrying the token counts a provider reports for one completion, so provider accounting crosses the `ILlmClient` boundary as typed integers instead of an opaque response object.

## Consumers
- [`LiteLLMAdapter`](../../adapters/outbound/litellm_adapter.md): Returns it from `get_token_usage`.
- [`PlanningService`](../services/planning_service.md): Reads it off the same completion response the cost lookup inspects and threads it into metadata persistence.
- [`PromptManager`](../services/prompt_manager.md): Persists its two counters into `meta.yaml` through `update_meta`.
- [`FakeLlmClient`](/tests/harness/setup/fake_llm_client.py): The harness double scripts and returns it as the fake `ILlmClient` usage branch.

## Dependencies
None — this is a domain value object with no injected collaborators.

## Class Invariants
- `frozen_value`: Instances are immutable and compare by value, so a usage reading cannot be mutated after the turn it describes.
- `absent_reads_as_zero`: Both counters default to `0`, so an unobservable count is never rendered as a cache estimate.
- `provider_accounting`: `prompt_tokens` is the provider's own input count, never the client's pre-call request estimate, which is persisted separately as `token_count` and drives the context-budget check.
- `no_ratio_assertion`: The type deliberately does not assert `cached_tokens <= prompt_tokens`, because a provider may count sub-blocks; clamping belongs to the display layer.

## Inbound Ports
None — this is a domain value object.

## Outbound Ports
None.

## Data Contracts
- **`prompt_tokens`** (`int`): The provider's reported input-token count, `0` when the provider reports nothing.
- **`cached_tokens`** (`int`): The portion of the input the provider served from its prompt cache, `0` when the provider reports no cache details.
- **Re-export**: The models package re-exports it, so consumers import it from `teddy_executor.core.domain.models`.

## Operations
### `TokenUsage(prompt_tokens=0, cached_tokens=0)`
- **Preconditions:** None.
- **Postconditions:** Returns an immutable value object holding both counts.
- **Exceptions:** None.
