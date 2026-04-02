# MRE: TUI Unresponsiveness & Focus Regressions

- **Status:** Resolved
- **Target File:** [prototypes/tui_deferred_harvest.py](/prototypes/tui_deferred_harvest.py)

## Failure Context
The refined TUI prototype intended to implement "Deferred Harvesting" (non-blocking external editing) suffers from systemic unresponsiveness when pushing `ModalScreen` components. User input (keys) is not captured by the modals, effectively locking the application. Additionally, the layout does not meet the specified information density and navigation requirements.

## Steps to Reproduce
1. Run the prototype: `python prototypes/tui_deferred_harvest.py`
2. **Scenario 1 (PROMPT Hang):**
   - Highlight the `PROMPT` action in the left tree.
   - Press `x` (Execute).
   - **Observed:** An overlay appears, but the TUI becomes unresponsive. Pressing `y` or `n` does nothing.
3. **Scenario 2 (Param Edit Hang):**
   - Highlight any action.
   - Tab into the right panel.
   - Press `e` (Edit) on a simple parameter (e.g., `overwrite`).
   - **Observed:** The `ParameterEditModal` appears, but the `Input` widget does not capture focus or text, and the UI hangs.
4. **Scenario 3 (Layout Issues):**
   - View the `ActionTree` (left pane) with long descriptions.
   - **Observed:** Horizontal scrollbars appear; text does not wrap.

## Expected vs. Actual Behavior

### 1. Modal Responsiveness
- **Expected:** `PromptOverlay` and `ParameterEditModal` should immediately capture focus. Keys like `y`, `n`, `enter`, and `escape` should work.
- **Actual:** TUI ignores key events after modal push, requiring a hard kill (`Ctrl+C`).

### 2. Focus Management
- **Expected:** Tabbing into the right panel should auto-focus the first element (or last focused).
- **Actual:** The panel receives focus but requires an extra click/navigation to activate items.

### 3. Text Wrapping
- **Expected:** `ActionTree` labels should wrap text to avoid horizontal scrolling.
- **Actual:** Labels are truncated or cause scrolling.

### 4. Semantic Wording
- **Expected:** Confirmation modal should ask "Save changes? y/n" instead of "Have you finished editing...".
- **Actual:** Current wording is verbose and confusing.

## Relevant Code
The following widgets in `prototypes/tui_deferred_harvest.py` are the primary suspects:
- `PromptOverlay(ModalScreen)`: Focus logic for the `Static` message.
- `ParameterEditModal(ModalScreen)`: `on_mount` focus logic for `Input`.
- `DeferredHarvestTui`: The `on_focus` and `action_edit_details` handlers.
- `ActionTree`: The label rendering logic and missing CSS for wrapping.

## Investigation Log
- **Observation:** In Textual, `Static` widgets require `can_focus = True` to receive key events.
- **Observation:** `ModalScreen` focus must be explicitly managed or the app may "fall through" to the base screen which is obscured.
- **Observation:** `Tree` labels in Textual do not natively wrap; they may require custom `Static` rendering within the tree or a different widget approach if wrapping is mandatory.
- **Observation:** `DeferredHarvestTui.on_focus` incorrectly accesses `event.node`, which is missing on `Focus` events (should be `event.control`). This `AttributeError` during focus transitions (modal push) hangs the async event loop.
- **Observation:** `ParameterDetail` (ListView) receives focus but does not automatically highlight the first child, leading to "Tab Hang" where the UI looks focused but keys don't work.
> **Hypothesis**: The TUI continues to hang during `EXECUTE` (`x`) or `EDIT` (`e`) actions even when `code` is available because the custom `push_screen_wait` helper using `asyncio.Future` deadlocks the Textual message pump.
> **Experiment**: Wrote an isolated pilot test (`spikes/debug/test_tui_hang.py`) simulating an `x` keypress to open the modal, followed by `y`. Tested substituting `asyncio.Future` with Textual's native `await app.push_screen()`.
> **Observation**: The `Future`-based implementation permanently blocked the event loop. The native Textual implementation correctly dismissed the modal.
> **Conclusion**: The custom `push_screen_wait` using `asyncio.Future` is flawed and directly causes the TUI deadlock. Textual's native awaitable must be used.
> **Hypothesis**: The TUI may also crash when pressing `x` if the root node (`Action Plan`) is selected, as it lacks a `.data` attribute.
> **Experiment**: Ran the pilot test, observing the stack trace when `x` was pressed on the root node.
> **Observation**: Caught an `AttributeError: 'NoneType' object has no attribute 'executed'` in `action_execute_step`.
> **Conclusion**: `action_execute_step` requires a `node.data` existence check.
- **Observation:** Replacing `push_screen_wait` with `push_screen` (as seen in `tui_deferred_harvest.py`) breaks the data flow because `push_screen` does not block and immediately returns `None` (or an awaitable depending on the version), failing to capture the user's confirmation.
> **Hypothesis:** Textual's native `push_screen_wait` MUST be used to correctly await modal dismissals, but it strictly requires the calling method to be executed within a worker thread to avoid deadlocking the main asyncio event loop.
> **Experiment:** Wrote a pilot test (`spikes/debug/test_work_modal.py`) using the `@work` decorator on the action handler and awaiting `push_screen_wait`.
> **Observation:** The test passed. The worker thread suspended gracefully while the main UI thread remained responsive to user input, successfully capturing the modal's return value.
> **Conclusion:** The core hang is caused by invoking blocking modal logic directly on the main UI event loop. All action handlers that invoke modals must be decorated with `@work`.

## Proposed Fix
- **Strategy:** Correct focus management and implement truncated labels in the `ActionTree`.
- **Changes:**
    1. Update `DeferredHarvestTui.on_focus` to use `event.control`.
    2. Add `on_mount` focus logic to `PromptOverlay` and `ParameterEditModal`.
    3. Truncate `ActionTree` labels to 60 characters to maintain density.
    4. Update `PromptOverlay` wording to "Save manual changes? (y/n)".

## Root Cause Analysis
There were multiple concurrent root causes for the TUI becoming unresponsive:

1. **Focus/Event Loop Unhandled Exceptions:** An `AttributeError` in the `DeferredHarvestTui.on_focus` handler (accessing `event.node` instead of `event.control`) caused silent failures during focus transitions. Additionally, an `AttributeError` in `action_execute_step` occurred when pressing `x` on the root node because it lacked a `data` attribute.
2. **Asynchronous Deadlock (Primary Cause of Editor Hang):** Action handlers (`action_edit_details`, `action_execute_step`) require the UI to suspend while waiting for a user response from a `ModalScreen`. Attempting to await custom Futures directly on the main event loop deadlocks the message pump. The subsequent attempt to use `await self.push_screen(screen)` failed because it does not block execution, causing the handler to continue with a `None` result before the user interacts with the modal. The handlers must be executed in a separate thread so they can suspend without blocking the UI.
3. **Focus Management:** Modal widgets lacked explicit focus logic, causing key events to fall through to the background screen.

## Implementation Notes
- **Deadlock Resolution:** Decorated action handlers with Textual's `@work` decorator to offload them to a worker thread. Used Textual's native `await self.push_screen_wait(screen)` to safely suspend the worker and capture the modal's return value.
- **Testing Caveats:** When verifying the prototype with a `Pilot`, triggering actions bound to `@work` handlers means the side-effects occur asynchronously. In previous attempts, `await app.workers.wait_for_complete()` immediately after `pilot.press("x")` did not consistently block until the worker finished (or the worker didn't start fast enough), leading to premature `AssertionError`s on state changes. Furthermore, UI focus state must be carefully managed in tests. Relying on `tab` and `shift+tab` keypresses to navigate complex layouts in headless tests is brittle and can lead to the pilot interacting with the wrong widget. If the test expects a `PromptOverlay` but actually opens a `ParameterEditModal`, pressing `y` will simply type text rather than dismissing the overlay, causing `app.workers.wait_for_complete()` to hang indefinitely (deadlock). To ensure robust testing, use `app.set_focus(widget)` to explicitly control focus before triggering keyboard bindings.
- **Modal Interactions:** Added `on_input_submitted` to `ParameterEditModal` to natively handle `enter` key submissions. Implemented a dedicated `EnterConfirmOverlay` for the `PROMPT` workflow to allow users to intuitively confirm with `enter` instead of `y`.
- **State Retention:** Updated the external editor dispatcher to reuse the `action.pending_temp_file` if it exists. This prevents state loss when a user presses `e` multiple times on the same action.
- **Tab Auto-Selection:** Configured the `ParameterDetail` pane to automatically set its `index = 0` whenever it is populated, ensuring that subsequent `tab` key navigations seamlessly enter an actionable state without requiring an extra keypress.
- **Validation Learnings:** A pilot test confirmed the `@work` fix prevents deadlocks. It also revealed that when `ParameterDetail` receives focus via Tab, it highlights the first element (index 0). Automated tests simulating keypresses must account for this ordered layout when validating data mutations. Furthermore, because `@work` tasks execute in a separate thread asynchronously, test runners must explicitly `await app.workers.wait_for_complete()` to ensure mutations have occurred before making assertions.
- **Event Attribute Safety:** Added `node.data` existence checks to all action handlers (e.g., `action_execute_step`) to prevent exceptions when interacting with the root node. Used `getattr(event, "control", None)` in focus handlers to safely distinguish between widget types.
- **Focus Consistency:** All `ModalScreen` components now use `on_mount` to explicitly focus their primary interactive widget.
- **Density via Truncation:** Implemented a 60-character truncation policy for the `ActionTree` to maintain information density, delegating detailed, wrapped text to the `ParameterDetail` pane.
