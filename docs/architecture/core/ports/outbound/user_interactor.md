# Component Design: IUserInteractor
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/ports/outbound/user_interactor.py`](/src/teddy_executor/core/ports/outbound/user_interactor.py)

## Purpose
Defines the outbound port for all user interaction: prompting for free text, confirming plans and actions, reporting skipped actions, and surfacing warnings. It isolates the core from the console, so adapters can render diffs, previews, and richer flows.

## Consumers
- `ActionExecutor`: Confirms each action before execution.
- [`PromptManager`](../../services/prompt_manager.md): Asks the user a question through the port.
- [`ActionPorts`](../../domain/action_ports.md): Carries the port into the action layer.
- [CLI Adapter](../../../adapters/inbound/cli.md): Provides the concrete console interaction.

## Dependencies
- **`Plan`**, **`ActionData`**, **`ChangeSet`** (`teddy_executor.core.domain.models`): Domain models exchanged by the confirmation flows (type-checking only).

## Class Invariants
- `abstract_base_class`: The port is an `ABC`; implementing adapters override every operation.
- `single_source_of_input`: Implementations own the input stream and must not leak stdin between calls.

## Inbound Ports
None — this is an outbound (driven) port.

## Outbound Ports
- **`IUserInteractor`**: The driven contract consumed by core services and implemented by the `ConsoleInteractor` adapter.

## Data Contracts
- **`confirm_action` return:** `(approved: bool, reason: str)`.
- **`confirm_manual_handoff` return:** `(approved: bool, rejection_reason: str)`.

## Operations

### `prompt(text, default="") -> str`
- **Preconditions:** `text` is a non-empty string.
- **Postconditions:** Returns the user's response, or `default` when input is empty.

### `ask_question(prompt, resources=None, agent_name=None) -> str`
- **Preconditions:** `prompt` is a non-empty string.
- **Postconditions:** Returns the user's free-text response; implementations support multi-line input.

### `display_message(message) -> None`
- **Preconditions:** None.
- **Postconditions:** Shows a non-interactive informational message.

### `confirm_plan_review(plan) -> bool`
- **Preconditions:** `plan` is a valid `Plan`.
- **Postconditions:** Returns `True` when the user approves the whole plan.

### `confirm_action(action, action_prompt, change_set=None) -> tuple[bool, str]`
- **Preconditions:** `action` is a valid `ActionData`; `action_prompt` is non-empty.
- **Postconditions:** Returns `(approved, reason)`; `reason` is empty when approved.

### `notify_skipped_action(action, reason) -> None`
- **Preconditions:** None.
- **Postconditions:** Reports that an action was skipped and why.

### `confirm_manual_handoff(action_type, target_agent, resources, message) -> tuple[bool, str]`
- **Preconditions:** `action_type` is `INVOKE` or `RETURN`.
- **Postconditions:** Returns `(True, "")` on approval, or `(False, reason)` on rejection.

### `notify_warning(message) -> None`
- **Preconditions:** None.
- **Postconditions:** Surfaces a non-fatal warning.
