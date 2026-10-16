# Component Design: Action Parser Strategies
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/services/action_parser_strategies.py`](/src/teddy_executor/core/services/action_parser_strategies.py)

## Purpose
A stateless module of strategy functions that parse individual action blocks for the `MarkdownPlanParser`. Each function consumes one action's nodes from a shared peekable stream and returns a populated `ActionData` object.

## Consumers
- [`MarkdownPlanParser`](./markdown_plan_parser.md): Dispatches the CREATE and READ action blocks to these strategies.

## Dependencies
- [`parser_infrastructure`](./parser_infrastructure.md): Supplies the `_PeekableStream` wrapper and the `coerce_action_params` helper.
- [`parser_metadata`](./parser_metadata.md): Supplies `parse_action_metadata` for the bulleted metadata list.
- `mistletoe` (external): Supplies the block tokens matched by the strategies (`List`, `CodeFence`), imported lazily inside each function.

## Class Invariants
- `stateless_module`: The module holds no mutable state; each function depends only on its arguments.
- `uniform_return`: Every strategy returns an `ActionData` carrying `type`, `description`, `params`, and `node`.
- `fail_fast`: A missing or malformed block raises `InvalidPlanError` immediately with the offending node attached.

## Inbound Ports
None — this module is an internal helper of `MarkdownPlanParser`.

## Outbound Ports
None — the module declares no injected dependencies.

## Data Contracts
- **`ActionData`** (`teddy_executor.core.domain.models`): The parsed action record produced by each strategy.
- **`InvalidPlanError`** (`teddy_executor.core.ports.inbound.plan_parser`): Carries the offending node for structural diagnostics.

## Operations

### `parse_create_action(stream, node=None) -> ActionData`
- **Preconditions:** The stream yields a Markdown list, then a content code fence.
- **Postconditions:** Returns a CREATE action carrying `path`, an optional coerced `overwrite` flag, and `content`.
- **Exceptions:** `InvalidPlanError` when the metadata list or the content block is missing.

### `parse_resource_action(stream, action_type, node=None) -> ActionData`
- **Preconditions:** The stream yields a Markdown list.
- **Postconditions:** Returns an action of the given type with `resource` resolved from a `Resource` link, falling back to a `File Path` value.
- **Exceptions:** `InvalidPlanError` when the metadata list is missing.

### `parse_read_action(stream, node=None) -> ActionData`
- **Preconditions:** The stream yields a Markdown list.
- **Postconditions:** Returns a READ action by delegating to `parse_resource_action`.
- **Exceptions:** `InvalidPlanError` when the metadata list is missing.
