# Extend the Greeting Helper
- **Agent:** Developer
- **Plan Type:** Implementation
- **Status:** ON-TRACK 🟢

## Rationale
~~~~~~
### Summary
The greeting module exists from the previous turn. We add a farewell helper alongside greet; a sibling function keeps the change small and testable, consistent with iterative delivery.

### Expectation
src/greeting.py gains a farewell function. The next plan wraps up the session.

### Progress
Goal: Build a greeting helper.
Reference Files: N/A

- [✓] Scaffold module and test
- [▶] Extend the helper

### Notes
- [TODO] Wrap up the session in the next plan.
~~~~~~

## Action Plan

### `EDIT`
- **File Path:** [src/greeting.py](/src/greeting.py)
- **Description:** Add a farewell helper next to greet.

#### `FIND:`
~~~~~~
def greet(name: str) -> str:
    """Return a personalized greeting message."""
    return f"Hello, {name}!"
~~~~~~
#### `REPLACE:`
~~~~~~
def greet(name: str) -> str:
    """Return a personalized greeting message."""
    return f"Hello, {name}!"


def farewell(name: str) -> str:
    """Return a personalized farewell message."""
    return f"Goodbye, {name}!"
~~~~~~
