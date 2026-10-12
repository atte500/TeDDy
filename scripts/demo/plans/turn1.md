# Scaffold a Greeting Module
- **Status:** Green 🟢
- **Plan Type:** Implementation
- **Agent:** Developer

## Rationale
````
1. Synthesis
The project has no greeting module yet. We scaffold the module and its test, following Test-Driven Development.

2. Justification
A failing test comes first, then the smallest implementation that satisfies it, keeping the feedback loop short.

3. Expectation
src/greeting.py and tests/test_greeting.py will exist. The next plan extends the helper.

4. State Dashboard
Goal: Build a greeting helper.

PHASES:
- [▶] Scaffold module and test
- [ ] Extend the helper
````

## Action Plan

### `CREATE`
- **File Path:** [src/greeting.py](/src/greeting.py)
- **Description:** Create the greeting module.
```
def greet(name: str) -> str:
    return f"Hello, {name}!"
```

### `CREATE`
- **File Path:** [tests/test_greeting.py](/tests/test_greeting.py)
- **Description:** Create the test for the greeting helper.
```
from src.greeting import greet


def test_greet() -> None:
    assert greet("World") == "Hello, World!"
```
