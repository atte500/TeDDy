# Extend the Greeting Helper
- **Status:** Green 🟢
- **Plan Type:** Implementation
- **Agent:** Developer

## Rationale
````
1. Synthesis
The greeting module exists. We add a farewell helper alongside greet.

2. Justification
A sibling function keeps the change small and testable, consistent with iterative delivery.

3. Expectation
src/greeting.py gains a farewell function. The next plan wraps up the session.

4. State Dashboard
Goal: Build a greeting helper.

PHASES:
- [✓] Scaffold module and test
- [▶] Extend the helper
````

## Action Plan

### `EDIT`
- **File Path:** [src/greeting.py](/src/greeting.py)
- **Description:** Add a farewell helper next to greet.

#### `FIND:`
```
def greet(name: str) -> str:
    return f"Hello, {name}!"
```
#### `REPLACE:`
```
def greet(name: str) -> str:
    return f"Hello, {name}!"


def farewell(name: str) -> str:
    return f"Goodbye, {name}!"
```
