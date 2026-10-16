# Component Design: PlanValidator
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/services/plan_validator.py`](/src/teddy_executor/core/services/plan_validator.py)

## Purpose
Implements the `IPlanValidator` inbound port. It performs pre-flight validation of a parsed `Plan` by dispatching every action to an injected, action-specific validator and accumulating a complete list of errors.

## Consumers
- [`ExecutionOrchestrator`](./execution_orchestrator.md): Validates an approved plan before execution begins.
- [CLI Adapter](../../adapters/inbound/cli.md): Drives validation in the manual `execute` flow.

## Dependencies
- [`IFileSystemManager`](../ports/outbound/file_system_manager.md): Stored for the validator strategies that inspect paths.
- [`IActionValidator`](/src/teddy_executor/core/services/validation_rules/helpers.py): The injected strategy protocol exposing `can_validate` and `validate`.
- [`ValidationError`](/src/teddy_executor/core/services/validation_rules/helpers.py): The error DTO accumulated by `validate`.

## Class Invariants
- `injected_strategies`: The validator list arrives through the constructor; the service never instantiates strategies itself.
- `accumulate_never_raise`: `validate` collects errors from every action and never raises; an empty list means success.
- `side_effect_free`: Validation reads state but never mutates the filesystem.

## Inbound Ports
- **`IPlanValidator`**: Exposes the single `validate(plan, context_paths=None)` operation.

## Outbound Ports
- **`IFileSystemManager`**: Consumed indirectly through the injected validator strategies.

## Data Contracts
- **`Plan`** (`teddy_executor.core.domain.models.plan`): The validated object.
- **`IActionValidator`** (`validation_rules.helpers`): Strategy protocol with `can_validate(action_type)` and `validate(action, context_paths)`.
- **`ValidationError`** (`validation_rules.helpers`): Carries `message` and `file_path`.

## Operations

### `PlanValidator(file_system_manager, validators=None)`
- **Preconditions:** `file_system_manager` implements `IFileSystemManager`.
- **Postconditions:** Stores the manager and the validator list, defaulting to an empty list when `validators` is `None`.

### `validate(plan, context_paths=None) -> List[ValidationError]`
- **Preconditions:** `plan` is a parsed `Plan`.
- **Postconditions:** Returns the accumulated `ValidationError` list. The method dispatches each action to the first injected validator whose `can_validate` matches; actions of type `research`, `prompt`, `invoke`, or `return` are accepted with no rules; a `message` action under `## Action Plan` yields a mutual-exclusivity error; any other unmatched action yields an unknown-action error.
- **Exceptions:** None — failures are returned as errors, never raised.
