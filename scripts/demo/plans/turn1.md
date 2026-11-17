# Scaffold a Greeting Module
- **Agent:** Developer
- **Plan Type:** Implementation
- **Status:** ON-TRACK 🟢

## Rationale
~~~~~~
### Summary
The project has no greeting module yet. Following Test-Driven Development, we scaffold the module and a failing test first, then the smallest implementation that satisfies it.

### Expectation
src/greeting.py and tests/test_greeting.py will exist and the scaffolded test will pass. The next plan extends the helper.

### Progress
Goal: Build a greeting helper.
Reference Files: N/A

- [▶] Scaffold module and test
- [ ] Extend the helper

### Notes
- [TODO] Extend the helper in the next plan.
~~~~~~

## Action Plan

### `CREATE`
- **File Path:** [src/greeting.py](/src/greeting.py)
- **Description:** Create the greeting module.
~~~~~~
def greet(name: str) -> str:
    return f"Hello, {name}!"
~~~~~~

### `CREATE`
- **File Path:** [tests/test_greeting.py](/tests/test_greeting.py)
- **Description:** Create the test for the greeting helper.
~~~~~~
from src.greeting import greet


def test_greet() -> None:
    assert greet("World") == "Hello, World!"
~~~~~~

### `EXECUTE`
- **Description:** Run test suite to verify initial setup.
- **Expected Outcome:** Tests pass.
~~~~~~
python -m unittest tests/test_greeting.py
~~~~~~
