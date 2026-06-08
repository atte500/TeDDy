# Slice: Double Newlines in Message Output
- **Status:** Completed
- **Type:** Feature
- **Milestone:** N/A (ad-hoc)
- **Component Docs:** [ConsoleInteractor](/docs/architecture/adapters/outbound/console_interactor.md)

## Business Goal
When an AI agent outputs a `## Message` block, the newlines in the message content should be doubled before display to the user. This provides better visual spacing and readability for multi-paragraph messages.

## Scenarios
> As a user, I want agent messages to have doubled newlines on display so that paragraphs are clearly separated for improved readability.

```gherkin
Given an agent has generated a plan with a "## Message" section
When the message is displayed to the user
Then each single newline in the message content is replaced with a double newline (`\n\n`)
```

## Edge Cases
- **Empty string**: If the message is empty, return an empty string without modification.
- **Already doubled newlines**: If a message already has `\n\n`, it should not be quadrupled (`\n\n\n\n`). The function should only replace single `\n` that are NOT already part of `\n\n`.
- **Trailing/leading newlines**: Trailing and leading newlines should be preserved (they may be intentional formatting).
- **Carriage returns**: `\r\n` sequences should be treated as newlines and doubled (but `\r` alone should not be modified).
- **Mixed content**: Messages with code blocks, Markdown formatting, or other special characters should only have their newlines doubled, not other transformations applied.

## Deliverables
- [x] **Logic** - Implement `double_newlines()` pure utility function with comprehensive unit tests for edge cases.
- [x] **Wiring** - Inject the newline doubling preprocessing call into `ConsoleInteractorAdapter.display_message()`.

## Implementation Notes

### Logic Deliverable
- **Function:** `double_newlines(text: str) -> str` in `src/teddy_executor/core/utils/string.py`
- **Algorithm:** Two-regex approach to handle all edge cases:
  1. `(?<!\r|\n)\n(?!\n)` → `\n\n` handles bare newlines not part of already-doubled pairs.
  2. `\r\n(?!\r\n)` → `\r\n\r\n` handles Windows-style line endings.
- **Test Coverage:** 9 unit tests covering: basic doubling, already-doubled, mixed, empty, no newlines, multiple lines, trailing/leading newlines, carriage returns.
- **Design Decision:** Pure function with zero side effects; no dependencies on external state or configuration.
- **Integration Status:** Applied in Wiring deliverable.

### Wiring Deliverable
- **Target:** `ConsoleInteractorAdapter.display_message()` in `src/teddy_executor/adapters/outbound/console_interactor.py`
- **Change:** Added inline import of `double_newlines` from `string.py` and called it on the message before passing to `self._console.print()`.
- **Test:** `test_display_message_doubles_newlines` in `tests/suites/unit/adapters/outbound/test_console_interactor.py` — verifies that `display_message` transforms `"line1\nline2"` to `"line1\n\nline2"`.
- **Design Decision:** Single injection point at the outbound port implementation. All 8 call sites (`planning_service`, `session_orchestrator`, `session_lifecycle_manager`) automatically benefit without modification.
- **Edge Cases Preserved:** `double_newlines()` handles empty strings, already-doubled newlines, `\r\n`, trailing/leading newlines — no regressions in callers.

## Implementation Plan
The feature requires two atomic deliverables:

### 1. Logic: `double_newlines()` utility function
- **Target:** `src/teddy_executor/core/utils/string.py`
- **Test:** `tests/suites/unit/core/utils/test_string_utils.py`
- **Description:** A pure function that takes a string and replaces single `\n` characters with `\n\n`, while avoiding doubling `\n` that are already part of `\n\n`.
- **Signature:** `def double_newlines(text: str) -> str:`

### 2. Wiring: Inject preprocessing into `ConsoleInteractorAdapter`
- **Target:** `src/teddy_executor/adapters/outbound/console_interactor.py`
- **Test:** Existing `test_console_interactor.py` suite
- **Description:** Import and call `double_newlines()` at the beginning of `display_message()` before passing the transformed text to `self._console.print()`.
- **Note:** This is the single injection point since ALL message display paths converge on `ConsoleInteractorAdapter.display_message()` (confirmed by grep: 8 call sites including `planning_service`, `session_orchestrator`, `session_lifecycle_manager`).
