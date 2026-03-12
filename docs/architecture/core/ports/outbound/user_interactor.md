# Outbound Port: User Interactor

**Motivating Slice:** [Slice 10: Implement `prompt` Action](../../slices/10-chat-with-user-action.md)

This port defines the contract for components that can interact with the user by asking questions and capturing their input. It abstracts the specific mechanism of interaction (e.g., console, GUI) from the core application logic.

---

## Interface Definition

### `ask_question(prompt: str) -> str`

**Status:** Implemented

*   **Description:**
    Displays a `prompt` string to the user and captures their free-text response. The implementation should expect and handle multi-line input.
*   **Preconditions:**
    *   `prompt` must be a non-empty string.
*   **Postconditions:**
    *   Returns a string containing the complete, multi-line response from the user.
*   **Returns:**
    *   `str`: The user's response.

---

### `confirm_action(action: 'ActionData', action_prompt: str) -> tuple[bool, str]`

**Status:** Refactored
**Motivating Slice:** [Slice 23: Foundational CLI Additions & Refactoring](../../../slices/executor/23-cli-ux-foundations.md)

*   **Description:**
    Displays a prompt describing an action and asks the user for `y/n` confirmation. If the user denies the action, it prompts them for an optional reason. The full `Action` object is passed to allow implementing adapters to provide enhanced previews (e.g., diffs for `edit` actions).
*   **Preconditions:**
    *   `action` must be a valid `ActionData` domain object.
    *   `action_prompt` must be a non-empty string describing the action to be confirmed.
*   **Postconditions:**
    *   Returns a tuple where the first element is a boolean indicating approval, and the second is the optional reason string provided by the user if the action was denied.
*   **Returns:**
    *   `tuple[bool, str]`: A tuple containing:
        *   `bool`: `True` if the user approved, `False` otherwise.
        *   `str`: The user's reason for denial, or an empty string if approved or no reason was given.

---

### `confirm_manual_handoff(action_type: str, target_agent: str | None, resources: list[str], message: str) -> tuple[bool, str]`

**Status:** Implemented
**Motivating Slice:** [Slice 10: CLI Orchestration Polish](../../../slices/10-cli-orchestration-polish.md)

*   **Description:**
    Displays a specialized instruction block for a manual handoff (`INVOKE` or `RETURN`) and captures user confirmation.
*   **Parameters:**
    *   `action_type`: The type of handoff ("INVOKE" or "RETURN").
    *   `target_agent`: The name of the agent being invoked (optional).
    *   `resources`: A list of file paths provided as handoff context.
    *   `message`: The verbatim handoff message.
*   **Returns:**
    *   `tuple[bool, str]`: `(True, "")` on approval (Enter), or `(False, reason)` if the user provides a rejection reason.

---

### `display_message(message: str) -> None`

**Status:** Implemented
**Motivating Slice:** [Slice 09-07: UX Polish & Logging](/docs/project/slices/09-07-ux-polish-logging.md)

*   **Description:**
    Displays a non-interactive message to the user. This is intended for status updates, telemetry, or other information that doesn't require a response but should be visible in the user's interface (e.g., printed to the console).
*   **Parameters:**
    *   `message`: The message to display.
