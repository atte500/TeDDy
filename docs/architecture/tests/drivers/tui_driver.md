# Component Design: TuiDriver
- **Status:** Implemented
- **Classification:** Test Driver
- **Source:** [`tests/harness/drivers/tui_driver.py`](/tests/harness/drivers/tui_driver.py)

## Purpose
Mounts the real `ReviewerApp` for a test and hands back the two things a reviewer scenario needs: an observation surface over the action tree, and a pilot whose tree holds focus. It exists because `run_test()` closes the app before returning, so no test could read the cursor, focus, or scroll offset while the app was alive.

## Consumers
- `tests/suites/unit/test_tui_driver.py`: Pins the driver's own contract — that each canonical panel shape reaches the mounted tree, and that `interaction()` yields a focused tree.
- `tests/suites/unit/adapters/inbound/test_section_navigation.py`: Walks the tree and resolves section membership over the canonical panel shapes.
- `tests/suites/acceptance/test_tui_section_boundaries.py`: Presses the jump keys to prove the subsection walk and the no-wrap boundary scrolls.
- `tests/suites/acceptance/test_tui_rationale_scrolling.py`: Steps through the tree to prove the right pane swaps to the rationale view.

## Dependencies
- [`TextualPlanReviewer`](../../adapters/inbound/textual_plan_reviewer.md): The reviewer boundary this driver mounts; its `ReviewerApp` is the widget under test, never a replacement for it.
- [`ActionTree`](../../adapters/inbound/textual_plan_reviewer.md): Queried by the observers and the widget every key press lands on.
- **`spec_mock`** (`tests.harness.setup.mocking`): Builds the spec-bound defaults for `ConsoleToolingHelper` and `ActionDispatcher`, so an omitted seam cannot answer an attribute it does not declare.
- [`ReviewerContextScenarios`](../setup/reviewer_context_scenarios.md): Supplies the `ProjectContext` shape a scenario injects and the plan it drives.

## Class Invariants
- `spec_bound_defaults`: An omitted `console_tooling` or `action_dispatcher` arrives as a `spec_mock` over the real seam type, never as a bare dynamic mock, so signature drift fails loudly instead of returning a silent child mock.
- `one_mount_path`: `run_interaction` delegates to `interaction()`, so key-driven scenarios and observation-driven scenarios share a single way of mounting the app.
- `observation_stays_inside`: The app is unmounted when `interaction()` exits, so every cursor, focus, or scroll assertion runs inside that block.
- `positional_compatibility`: `project_context`, `action_dispatcher`, and the doubled ports were added as keyword-only parameters while `console_tooling` kept its fourth positional slot, so every pre-existing construction site compiles unchanged.

## Inbound Ports
- **`interaction()`**: An async context manager yielding a `Pilot` whose `ActionTree` holds focus.
- **`tree(pilot)`**: Returns the mounted `ActionTree`.
- **`cursor_data(pilot)`**: Returns the payload of the node the cursor sits on, or `None` when no node is under it.
- **`run_interaction(keys)`**: Mounts the app, presses each key, and returns the app's resulting plan.
- **`set_input(pilot, selector, value)`**: Fills an `Input` on the active screen and submits it.
- **`get_active_view_id(pilot)`**: Returns the `ContentSwitcher`'s current view id.
- **`get_markdown_content(pilot)`**: Returns the mounted `Markdown` widget's text.

## Outbound Ports
None — the driver forwards the ports it is handed (`system_env`, `file_system`, `console_tooling`, `action_dispatcher`) into the app rather than consuming them itself.

## Data Contracts
- **`Plan`** and **`ProjectContext`**: Forwarded to the app under test. Passing `project_context=None` is how a scenario reaches the context-less panel shape.
- **`Pilot`** (`textual.pilot`): The handle every observer and key press takes.

## Operations

### `interaction() -> AsyncIterator[Pilot]`
- **Preconditions:** None.
- **Postconditions:** Yields a pilot for a mounted app whose tree holds focus, and unmounts the app when the block exits.

### `run_interaction(keys) -> Optional[Plan]`
- **Preconditions:** `keys` names key combinations the app binds.
- **Postconditions:** Returns the app's plan after every key ran. Navigational keys skip the worker wait; other keys wait for pending workers while the main screen is active, because a modal blocks on its own dismissal.

### `tree(pilot) -> ActionTree` and `cursor_data(pilot) -> Any`
- **Preconditions:** `pilot` came from `interaction()`.
- **Postconditions:** Return the mounted tree and the cursor's payload respectively; `cursor_data` returns `None` when no node sits under the cursor.

### `set_input(pilot, selector, value) -> None`
- **Preconditions:** The active screen carries an `Input` matching `selector`.
- **Postconditions:** The input holds `value` and its submit ran.
