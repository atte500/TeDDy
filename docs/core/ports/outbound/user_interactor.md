# Outbound Port: `IUserInteractor`

**Motivating Slice:** [Slice 10: Implement `chat_with_user` Action](../../slices/10-chat-with-user-action.md)

This port defines the contract for components that can interact with the user by asking questions and capturing their input. It abstracts the specific mechanism of interaction (e.g., console, GUI) from the core application logic.

---

## Interface Definition

### `ask_question(prompt: str) -> str`

**Status:** Planned

*   **Description:**
    Displays a `prompt` string to the user and captures their free-text response. The implementation should expect and handle multi-line input.
*   **Preconditions:**
    *   `prompt` must be a non-empty string.
*   **Postconditions:**
    *   Returns a string containing the complete, multi-line response from the user.
*   **Returns:**
    *   `str`: The user's response.
