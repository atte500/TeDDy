# MRE: TUI View Plan Suspension Failure
- **Status:** Resolved

## 1. Failure Context
The `ReviewerApp.action_view_plan` method, which allows a user to view the full plan in an external editor, fails during acceptance tests. The failure occurs specifically when the plan is provided as raw content (e.g., from the clipboard) and does not have an associated file path. The external editor is never launched because the TUI suspension feature, required for terminal-based editors, is not supported by Textual's headless test driver.

## 2. Steps to Reproduce
1. Run the specific acceptance test designed to cover this scenario:
   ```shell
   poetry run pytest tests/suites/acceptance/test_tui_view_plan_robustness.py
   ```
2. Observe the test execution and its final status.

## 3. Expected vs. Actual Behavior
- **Expected:** The test should pass. The mocked `run_command` method, which represents launching an external editor, should be called with the correct editor command and a path to a temporary file containing the plan's content.
- **Actual:** The test fails. The assertion `mock_env.run_command.assert_called_once_with(...)` is never reached or fails because `run_command` is not called.

## 4. Relevant Code
```python
# src/teddy_executor/adapters/inbound/textual_plan_reviewer.py
# In ReviewerApp class:

@work
async def action_view_plan(self) -> None:
    # ... fallback logic to get plan content ...
    if content:
        await self._launch_editor(content, suffix=".md")

async def _launch_editor(self, initial_content, suffix):
    # ... logic to create temp file ...
    # ...
    # The call to self.suspend() raises SuspendNotSupported in tests
    with self.suspend():
        self._system_env.run_command(editor_cmd + [temp_file])
```

## 5. Investigation Log
- **2026-03-30 (Previous Investigation):**
    - **Hypothesis:** `action_view_plan` has a logic error preventing it from calling `_launch_editor`.
    - **Experiment:** Ran `test_tui_view_plan_robustness.py`.
    - **Observation:** Test failed because `run_command` was never called. Debugging revealed a `SuspendNotSupported` exception is raised internally by the Textual test harness when `app.suspend()` is called.
    - **Conclusion:** The failure is due to a limitation in the test environment, not a bug in the application's production logic. A potential fix involves patching `ReviewerApp.suspend` within the test itself.
- **2026-03-30 (Current Investigation):**
    - **Hypothesis:** The provided test case `tests/suites/acceptance/test_tui_view_plan_robustness.py` will fail as described, despite containing what appears to be a patch for the issue.
    - **Experiment:** Executing the test via `spikes/debug/reproduce_tui_failure.sh`.
    - **Observation:** The test failed with `AssertionError: Expected 'run_command' to be called once. Called 0 times.`. This confirms the bug is reproducible and the existing patch in the test file is ineffective.
    - **Conclusion:** The failure is happening inside the `_launch_editor` background worker. The `no_op_suspend_cm` patch is insufficient. A silent exception is the most likely cause.
    - **Next Step:** Instrument `_launch_editor` with extensive logging to trace execution and expose any hidden exceptions.
- **2026-03-30 (Error Investigation):**
    - **Experiment:** Re-ran test after adding `self.log()` calls to `_launch_editor`.
    - **Observation:** The test failed again, but **no log messages appeared in the pytest output**.
    - **Conclusion:** The test harness itself is suppressing the application logs. I cannot debug the application without visibility.
    - **Next Step:** Modify the test execution script to enable Textual's file logging via the `TEXTUAL_LOG` environment variable and dump the log contents to `stdout`.

## 6. Root Cause Analysis
**Verified:** The root cause is a type mismatch in the test's mocking strategy.

1.  The application code in `_launch_editor` calls `with self.suspend():`. This is a standard, **synchronous** context manager invocation. The real `app.suspend()` method provides a synchronous context manager.
2.  The test `test_tui_view_plan_robustness.py` patches this method using `patch.object(app, "suspend", return_value=no_op_suspend_cm())`.
3.  The mock context manager, `no_op_suspend_cm`, is defined with `@asynccontextmanager`, making it an **asynchronous** context manager.
4.  When the application's synchronous `with` statement attempts to use the provided asynchronous context manager, Python correctly raises a `TypeError: '_AsyncGeneratorContextManager' object does not support the context manager protocol`.
5.  This `TypeError` is caught by the `except Exception` block within `_launch_editor` and silently logged (as seen in the debug logs), preventing the `run_command` mock from ever being called and causing the test assertion to fail.

The bug is therefore not in the application code but in the test setup itself.

## 7. Implementation Notes
- **Fix Strategy:** The fix was implemented entirely within the test suite, as the root cause was a faulty test mock, not an application bug.
- **Implementation:** The `no_op_suspend_cm` helper in `tests/suites/acceptance/test_tui_view_plan_robustness.py` was changed from an `@asynccontextmanager` to a standard `@contextmanager`. This resolved the `TypeError` by ensuring the mock's type signature matched the synchronous method it was patching in the application code.
- **Cleanup:** All diagnostic logging and spike scripts have been removed.
