# Component Design: IPlanReviewer
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/ports/inbound/plan_reviewer.py`](/src/teddy_executor/core/ports/inbound/plan_reviewer.py)

## Purpose
Defines the inbound port for interactive review and modification of a `Plan` before execution. It lets a human-in-the-loop toggle actions or edit parameters. The port is implemented by the `TextualPlanReviewer` primary adapter.

## Consumers
- [`ExecutionOrchestrator`](../../services/execution_orchestrator.md): Invokes review before executing an interactive plan.

## Dependencies
- **`Plan`** and **`ActionData`** (`teddy_executor.core.domain.models.plan`): The reviewed objects.
- **`ProjectContext`** (`teddy_executor.core.domain.models.project_context`): Optional display metadata.

## Class Invariants
- `runtime_checkable`: The protocol supports `isinstance` checks.

## Inbound Ports
- **`IPlanReviewer`**: Exposes `review(...)` and `review_action(...)`.

## Outbound Ports
None — the port declares no injected dependencies.

## Data Contracts
- **`Plan`**, **`ActionData`**, and **`ProjectContext`**: Domain models exchanged by the review flow.

## Operations

### `review(plan, project_context=None) -> Optional[Plan]`
- **Preconditions:** `plan` is a valid `Plan`.
- **Postconditions:** Returns a `Plan` carrying the user's selections and edits, or `None` when the user cancels.

### `review_action(action, total_actions, agent_name=None) -> tuple[bool, str]`
- **Postconditions:** Returns `(should_execute, captured_message)`.
