**Status:** Implemented

## 1. Purpose / Responsibility
Defines the contract for the interactive review and modification of a `Plan` domain object. This component bridges the gap between the static plan and its final execution by allowing a human-in-the-loop to selective enable/disable actions or modify their parameters. It supports both bulk review (TUI) and sequential review (Console).

## 2. Ports
This component is an **Inbound Port**. It is implemented by primary adapters that provide a User Interface (e.g., TUI or CLI).

## 3. Implementation Details
The implementation should:
1. Present the `Plan` (or individual `ActionData`) to the user.
2. Allow toggling the "Selected" state of each `ActionData`.
3. Provide a mechanism to modify action parameters (e.g., file paths or content).
4. Return the final selection/modification state to the caller.

## 4. Data Contracts / Methods

### `review(self, plan: Plan, project_context: Optional[ProjectContext] = None) -> Plan | None`
- **Description:** Initiates the interactive review process (bulk or TUI), optionally displaying project context and token counts.
- **Preconditions:**
  - `plan` must be a valid `Plan` object.
- **Postconditions:**
  - Returns a `Plan` object containing the user's modifications and selections.
  - Returns `None` if the user cancels or quits the review process.

### `review_action(self, action: ActionData, total_actions: int, agent_name: str | None = None) -> bool`
- **Description:** Initiates a sequential interactive review for a single action.
- **Returns:** `True` if the action should be executed, `False` if skipped.
