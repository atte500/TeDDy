# Bug: Slow Test Suite Optimization
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
The test suite takes an unacceptable amount of time to execute, hindering the development feedback loop.

## System Model
### Understanding
The project uses `pytest` with `pytest-xdist` for parallel execution (via `-n auto`). Tests are categorized into acceptance, integration, and unit suites.

### Discrepancies
None. Root cause identified as linear typing overhead in `pilot.press(*str)`.

### Understanding
The `Textual` testing pilot introduces a mandatory delay for every character in a `press(*str)` call to ensure event loop synchronization. This makes typing paths or commands in tests extremely slow (~3.3s per 50 chars).

### Planned Fixes
1.  **Harness Optimization:** Add `set_input(selector, value)` to `TuiDriver` which directly sets `Widget.value` and then presses "enter".
2.  **Test Refactoring:** Update identified slow tests to use `set_input` or direct value assignment instead of `pilot.press(*str)`.

## Solution
### Implemented Fixes
- Added `TuiDriver.set_input` method for high-speed simulated input in TUI tests.
- Refactored `test_tui_save_as_workflow.py`, `test_reviewer_app_modifications.py`, `test_reviewer_app_create_workflow.py`, and `test_reviewer_app_previews.py` to use direct `Input.value` assignment instead of `pilot.press(*str)`.
- Replaced `wait_for_scheduled_animations()` with faster `pilot.pause()` calls where appropriate.

### Prevention
- Use the `TuiDriver.set_input` method or direct `Input.value` assignment for all future TUI tests involving text entry to avoid the linear overhead of character-by-character typing.
