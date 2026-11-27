# Component Design: Plan
- **Status:** Implemented
- **Classification:** Core Domain
- **Source:** [`src/teddy_executor/core/domain/models/plan.py`](/src/teddy_executor/core/domain/models/plan.py)

## Purpose
The parsed plan pair: `Plan` carries a title, its rationale, and the ordered actions to run, while `ActionData` describes one action together with the reviewer's in-memory edits and the outcome it produced. Both stay mutable because the reviewer updates them while the plan is being approved.

## Consumers
- [`MarkdownPlanParser`](../services/markdown_plan_parser.md): Builds the plan from the authored Markdown.
- [`ExecutionOrchestrator`](../services/execution_orchestrator.md): Iterates the actions, stamps each one as it resolves, and orders the report by that stamp.
- [`TextualPlanReviewer`](../../adapters/inbound/textual_plan_reviewer.md): Selects, edits, and hand-executes actions in place.
- [`PlanValidator`](../services/plan_validator.md): Rejects a plan whose actions cannot run.

## Dependencies
None — pure domain models with no injected collaborator.

## Class Invariants
- `at_least_one_action`: A `Plan` asserts a non-empty action sequence on construction, so a plan that resolves to no work cannot exist.
- `sequence_recorded_at_resolution`: `ActionData.execution_sequence` is `None` until its action is resolved, and no parser, validator, or action factory assigns it. The orchestrator loop and the reviewer's manual path both stamp through `Plan.next_execution_sequence()`, so a plan whose actions were partly hand-executed before submission reports the order its actions actually ran rather than the order they sit in.
- `highest_stamp_plus_one`: `next_execution_sequence()` returns the highest recorded stamp plus one, and `1` when nothing is stamped. It follows the highest stamp rather than the count of stamped actions, so a gap or a duplicate left behind never causes a number to be reused.

## Inbound Ports
None — the models are data, not a service contract.

## Outbound Ports
None.

## Data Contracts
- **`ActionType`**: The `CREATE`, `READ`, `EDIT`, `EXECUTE`, `RESEARCH`, and `MESSAGE` action kinds.
- **`ExecutionStatus`**: The reviewer-visible per-action state (`PENDING`, `RUNNING`, `SUCCESS`, `FAILURE`, `SKIPPED`), distinct from the report's `ActionStatus`.
- **`ActionData`**: The action kind, its params, the reviewer's `selected`/`modified` bookkeeping, the recorded outcome (`executed`, `state`, `action_log`), and `execution_sequence: int | None`. The `is_terminal` property reports whether the action is a communicating turn.
- **`Plan`**: The title, rationale, action sequence, metadata, session flags, and the plan path the session scope derives from.
- **`ValidationError`**: The structured rejection a validator returns, carrying the message, the offending action index, the file path, and the offending AST node.

## Operations

### `is_communication_turn() -> bool`
- **Preconditions:** None.
- **Postconditions:** Returns `True` only when the plan holds a single `MESSAGE` action, which is what lets the orchestrator skip the reviewer and the console stay silent for a conversational turn.

### `next_execution_sequence() -> int`
- **Preconditions:** None.
- **Postconditions:** Returns the number the next resolved action must record: the highest `execution_sequence` among the plan's actions plus one, and `1` when no action is stamped.

### `is_terminal` (property)
- **Preconditions:** None.
- **Postconditions:** Returns `True` when the action is a communicating turn; the dispatcher and the skip notice both read it to stay silent for one.
