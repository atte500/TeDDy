# Bug: Test mock missing get_session_state return value causes ValueError
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
- **Actual:** `ValueError: not enough values to unpack (expected 2, got 0)` when running `test_lifecycle_manager_does_not_print_initial_request_on_subsequent_turns`.
- **Expected:** The test passes without error, verifying that `_print_initial_request` is not called for non-first turns.

### Reproduction
Run: `poetry run pytest tests/suites/unit/core/services/test_bug_03_prompt_resolution.py::TestLifecyclePrintsInitialRequest::test_lifecycle_manager_does_not_print_initial_request_on_subsequent_turns`

## Context & Scope
### Regressing Delta
The test file `tests/suites/unit/core/services/test_bug_03_prompt_resolution.py` was introduced as part of Bug #03 (initial request duplication fix). The failing test `test_lifecycle_manager_does_not_print_initial_request_on_subsequent_turns` mocks `ports.session_service` as a plain `MagicMock()` without configuring `get_session_state.return_value`. The port `ISessionManager` requires `get_session_state` to return `tuple[SessionState, str]`, but the mock returns a default MagicMock which yields zero elements when iterated, causing the ValueError.

### Environmental Triggers
- Running pytest on macOS with Python 3.11.14.
- The test is part of the unit test suite for core/services.

### Ruled Out
- `SessionService.get_session_state` implementation is correct (returns a valid tuple).
- `SessionLifecycleManager._handle_planning_and_execution` is correct (relies on port contract).
- The other tests in the same file (`test_lifecycle_manager_prints_initial_request`, `test_print_initial_request_resolves_path_with_parent`, etc.) pass because they either have correct mock setup or don't exercise the failing code path.

## Diagnostic Analysis
### Causal Model
`SessionLifecycleManager._handle_planning_and_execution` (line 138) calls:
```python
_, actual_turn_path = self._session_service.get_session_state(new_name)
```
This expects the outbound port `ISessionManager.get_session_state` to return a `tuple[SessionState, str]`. In the test, `ports.session_service` is a plain `MagicMock()` with no `get_session_state` return value configured. When `get_session_state` is called, it returns another `MagicMock` object. Python attempts to unpack this object into two variables, but since the MagicMock is iterable but yields no elements, it raises `ValueError: not enough values to unpack`.

The sibling test `test_lifecycle_manager_prints_initial_request` does NOT hit this code path because `resume()` is called instead of `_handle_planning_and_execution` directly. The resume method may check session state before calling `_handle_planning_and_execution`, but the external mock setup in that test happened to provide a return value for `get_session_state` (unintentionally covering the path). The failing test directly calls `_handle_planning_and_execution` with turn "02", bypassing any initial checks, and encounters the unpacking error.

### Discrepancies
- Test mock `ports.session_service` has no `get_session_state.return_value` configured. (Resolved: root cause identified.)

### Investigation History
1. Ran `poetry run pytest`, observed single failure with `ValueError: not enough values to unpack`.
2. Read `session_lifecycle_manager.py:138`: confirmed unpacking of `get_session_state` result.
3. Read port interface `ISessionManager`: confirmed signature `tuple[SessionState, str]`.
4. Read `SessionService.get_session_state`: returns proper tuple.
5. Read test file: confirmed `ports.session_service = MagicMock()` with no return_value.
6. Created MRE (`spikes/debug/04-lifecycle-mre.py`): reproduced the error by mimicking test setup.
7. Conclusion: root cause is incomplete test mock configuration.

## Solution
### Root Cause
The test mocks `ports.session_service` as a plain `MagicMock()` without setting `get_session_state.return_value` to a valid tuple. This violates the expected contract of the `ISessionManager` port.

### Fix
In the test, configure `get_session_state.return_value` to return a valid tuple in the `test_lifecycle_manager_does_not_print_initial_request_on_subsequent_turns` method:
```python
ports.session_service.get_session_state.return_value = (SessionState.EMPTY, "/some/path")
```

### Categorical Audit
**Abstract Category:** "Bare `MagicMock()` for port dependencies without configuring required method return values" — a form of mock poisoning where the mock does not fulfill the port contract expected by the production code.

**Audit Results (tests/suites/unit/core/services/):**
- The `MagicMock()` pattern for port objects is widespread in the test suite (at least ~120 occurrences in services unit tests). Most follow the pattern `ports.X = MagicMock()`. However, **critical port methods** that are actually called during the test are typically configured with `return_value` in the same block.
- The specific pattern of *not* configuring a required method that gets called during the test (like `get_session_state`) is rare. Most tests that exercise code paths calling `get_session_state` do configure it.
- The failing test `test_lifecycle_manager_does_not_print_initial_request_on_subsequent_turns` was a new test added as part of Bug #03. It directly calls `_handle_planning_and_execution`, which internally calls `get_session_state`. The mock was set up without configuring this return value because the test author didn't trace the full call chain.
- No other instances of port method calls missing `return_value` were found in the same test file or its siblings.

**Impact Audit:** The fix is confined to the test file `test_bug_03_prompt_resolution.py`. No production code changes are required. All existing consumers of the `ISessionManager` port are unaffected.

### Preventative Measures
- **Mandatory port mock configuration convention:** When mocking port dependencies in tests, configure return values for all methods that the production code under test may call. Use `create_autospec(ISessionManager)` when mocking `session_service` to automatically detect missing attributes.
- **Test helper fixture:** Add a reusable `ports_fixture` that provides pre-configured port mocks with sensible defaults, reducing the chance of missing configurations in new tests.
- **Code review checklist:** Add "All port mocks have required return values configured for the tested code path" to the review checklist.
- **Architecture enforcement:** Consider using a linting rule or test that verifies no port Protocol method is called on a MagicMock without a configured `return_value` (though this is hard to implement statically).
