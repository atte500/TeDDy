# Component Design: Model Identity
- **Status:** Implemented
- **Classification:** Core Utility
- **Source:** [`src/teddy_executor/core/utils/model_identity.py`](/src/teddy_executor/core/utils/model_identity.py)

## Purpose
A stateless module that splits a LiteLLM model string into the display name and provider the reviewer's Context panel states. Provider is a pure function of the model name, so no adapter call is needed and no second copy of the value is stored.

## Consumers
- [TextualPlanReviewer](../../adapters/inbound/textual_plan_reviewer.md): Derives the panel's Model and Provider rows from the DTO's `model_name` at render time.

## Dependencies
None. The module imports only the standard library (`typing`).

## Class Invariants
- `stateless_pure_functions`: The splitter is a pure function of its argument.
- `first_separator_wins`: The string partitions on the first `/` only, so a nested provider segment (`openrouter/~deepseek/deepseek-flash-latest`) keeps its inner slash in the display name.
- `no_invented_provider`: A provider-less model, a blank provider segment, and an empty remainder all report `unknown` rather than naming a provider the string does not carry.
- `placeholders_never_blank`: An unresolved model reports the `Unknown` / `unknown` placeholders, so the panel never renders an empty cell.

## Inbound Ports
None — this module is an internal helper surface.

## Outbound Ports
None — the module declares no injected dependencies.

## Data Contracts
- **Model identity tuple**: `(name, provider)` — the display name with its provider segment removed, and that provider segment, or the placeholders.
- **`UNKNOWN_MODEL_NAME` / `UNKNOWN_PROVIDER`**: The `Unknown` and `unknown` placeholder literals.

## Operations

### `split_model_identity(model) -> tuple[str, str]`
- **Preconditions:** `model` is the resolved model string, or `None` when nothing resolved.
- **Postconditions:** Returns `(name, provider)` for a `provider/model` string, `(name, "unknown")` for a provider-less one, and `("Unknown", "unknown")` for a blank or unresolved one. A blank `model` never yields an empty name.
- **Exceptions:** None.
