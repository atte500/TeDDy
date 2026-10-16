# Component Design: ActionDispatcher
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/services/action_dispatcher.py`](/src/teddy_executor/core/services/action_dispatcher.py)

## Purpose
Resolves one validated `ActionData` object to an executable handler through the `ActionFactory`, runs it, normalizes the raw result, and returns a structured `ActionLog`. It isolates the execution loop from the concrete action implementations.

## Consumers
- [`ActionExecutor`](/src/teddy_executor/core/services/action_executor.py): Dispatches each action while a plan executes.
- [`TextualPlanReviewer`](../../adapters/inbound/textual_plan_reviewer.md): Executes a single action from the interactive reviewer.
- [Composition Root](/src/teddy_executor/container.py): Constructs the dispatcher and injects its factory.

## Dependencies
- **`IActionFactory`** (`teddy_executor.core.services.action_dispatcher`): The injected collaborator that creates action handlers. It is declared as a `Protocol` in this module.

## Class Invariants
- `factory_driven`: The dispatcher never instantiates action handlers; every handler arrives through `IActionFactory`.
- `never_raises`: `dispatch_and_execute` catches every execution exception and records it as a `FAILURE` `ActionLog`.
- `parameter_normalization`: Markdown-friendly keys are remapped before execution (`file_path` to `path` for CREATE and EDIT; `source` and `resource` to `path` for READ), and any key prefixed with `metadata_` is dropped.
- `message_logging_suppressed`: A `MESSAGE` action skips the informational progress logging.

## Inbound Ports
None — the dispatcher is a concrete service consumed directly by its callers.

## Outbound Ports
None — its single collaborator is the internal `IActionFactory` protocol, not an outbound port.

## Data Contracts
- **`ActionData`** (`teddy_executor.core.domain.models.plan`): The action to execute.
- **`ActionLog`** (`teddy_executor.core.domain.models.execution_report`): The recorded outcome.
- **`ActionStatus`** (`teddy_executor.core.domain.models.execution_report`): The per-action status enum.
- **`ShellOutput`** (`teddy_executor.core.domain.models.shell_output`): Read for `return_code` and `interrupted` when an action returns shell output.

## Operations

### `ActionDispatcher(action_factory)`
- **Preconditions:** `action_factory` implements `IActionFactory`.
- **Postconditions:** Stores the factory.

### `dispatch_and_execute(action_data, agent_name=None) -> ActionLog`
- **Preconditions:** `action_data` is a validated `ActionData`.
- **Postconditions:** Returns an `ActionLog`. A dataclass result is converted with `asdict`; a string result from READ becomes `{"content": ...}`; a list result from EDIT becomes `{"similarity_scores": ...}`. A `ShellOutput` whose `interrupted` flag is set yields `ActionStatus.INTERRUPTED`; a non-zero `return_code` yields `FAILURE`; otherwise `SUCCESS`.
- **Exceptions:** None — every failure is captured in the returned `ActionLog`.
