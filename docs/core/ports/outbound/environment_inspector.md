# Outbound Port: `IEnvironmentInspector`

**Status:** Implemented
**Introduced in:** [Slice 13: Implement `context` Command](../../slices/13-context-command.md)

## 1. Responsibility

The `IEnvironmentInspector` port defines a technology-agnostic interface for gathering information about the user's operating environment, such as the operating system, Python version, and current working directory.

## 2. Methods

### `get_environment_info`
**Status:** Implemented

*   **Description:** Gathers key information about the system environment.
*   **Signature:** `get_environment_info() -> dict[str, str]`
*   **Preconditions:** None.
*   **Postconditions:**
    *   Returns a dictionary where keys are property names (e.g., "os_name") and values are the corresponding system details.

## 3. Related Spikes

*   N/A
