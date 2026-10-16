# Component Design: IPlanValidator
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/ports/inbound/plan_validator.py`](/src/teddy_executor/core/ports/inbound/plan_validator.py)

## Purpose
Defines the inbound port for pre-flight validation of a `Plan` before execution. In session-aware mode it validates action targets against the current working context. The port is implemented by the `PlanValidator` service.

## Consumers
- [`ExecutionOrchestrator`](../../services/execution_orchestrator.md): Runs validation before executing an approved plan.
- [CLI Adapter](../../../adapters/inbound/cli.md): Drives validation in the manual `execute` flow.

## Dependencies
- **`Plan`** (`teddy_executor.core.domain.models.plan`): The validated object.

## Class Invariants
- `side_effect_free`: Validation must not modify the filesystem.

## Inbound Ports
- **`IPlanValidator`**: Exposes the single `validate(...)` operation.

## Outbound Ports
None — the port declares no injected dependencies.

## Data Contracts
- **`ValidationError`** (DTO): `action_index: int` and `message: str`.

## Operations

### `validate(plan, context_paths=None) -> list[ValidationError]`
- **Preconditions:** `plan` is a valid `Plan`.
- **Postconditions:** Returns the accumulated `ValidationError` list; an empty list means the plan passed.
- **Exceptions:** None — failures are returned, not raised.
