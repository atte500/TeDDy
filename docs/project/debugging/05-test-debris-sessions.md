# Bug: Test Creates Debris in .teddy/sessions/test
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** [00-06-fix-test-debris-port-bypass](/docs/project/slices/00-06-fix-test-debris-port-bypass.md)
- **Specs:** N/A

## Symptoms
- **Expected:** Running tests should not create files or directories outside of temporary directories.
- **Actual:** The directory `.teddy/sessions/test/` exists in the project root with an empty `history.log` file.
- **Reproduction Steps:**
  1. Run the test suite (or specific unit tests that use `.teddy/sessions/test` as a hardcoded path).
  2. Observe that `.teddy/sessions/test/` is created in the project root.
  3. The directory contains an empty `history.log` file.

## Context & Scope
### Regressing Delta
The debris is caused by unit tests that use the hardcoded path `.teddy/sessions/test` instead of a temporary directory. The `.gitignore` has `.teddy` at the bottom, which hides the debris from git status.

### Environmental Triggers
- Running any test that references `.teddy/sessions/test` as a hardcoded path.
- The tests that use this path are:
  - `tests/suites/unit/core/services/test_bug_03_prompt_resolution.py`
  - `tests/suites/unit/core/services/test_bug_15_empty_message_termination.py`
  - `tests/suites/unit/core/services/test_session_orchestrator_empty_message.py`

### Ruled Out
- The debris is not tracked by git (`.teddy` is gitignored).
- The `history.log` file is empty, suggesting a session was initialized but never used.

## Diagnostic Analysis
### Causal Model
The root cause is in `SessionLifecycleManager._handle_planning_and_execution()` (lines 110-120 of `session_lifecycle_manager.py`). When `tee_active` is `False`, the method computes `log_path = Path(turn_dir).parent / "history.log"` and creates a `_Tee(log_path)` instance. The `_Tee.__enter__()` method calls `self._log_path.parent.mkdir(parents=True, exist_ok=True)`, which creates the `.teddy/sessions/test/` directory on the real filesystem, and then opens the file for appending, creating the empty `history.log`.

The critical architectural violation: `SessionLifecycleManager` bypasses the injected `_file_system_manager` port and uses direct `Path` operations to create the `history.log` file. This means even when all ports are mocked (as in the unit tests), the real filesystem is still accessed.

The test `test_lifecycle_manager_prints_initial_request` in `test_bug_03_prompt_resolution.py` triggers this path because:
1. It creates a `SessionLifecycleManager` with `MagicMock()` for all ports
2. The mock `session_service.get_session_state` returns `(".teddy/sessions/test/01", SessionState.EMPTY)`
3. `resume()` enters the `EMPTY` branch and calls `_handle_planning_and_execution(".teddy/sessions/test/01", ...)`
4. Inside `_handle_planning_and_execution`, `tee_active` is `False`, so it creates the `_Tee` with `Path(".teddy/sessions/test") / "history.log"`
5. `_Tee.__enter__()` creates the directory and file on the real filesystem

### Discrepancies
- The `.teddy/sessions/test/` directory exists with an empty `history.log` file, but git status shows clean. (Resolved: `.teddy` is gitignored.)
- The unit tests mock `IFileSystemManager`, but the directory still gets created. (Resolved: `SessionLifecycleManager` bypasses the mocked port and uses direct `Path` operations via `_Tee`.)

### Investigation History
1. Confirmed `.teddy/sessions/test/` exists with empty `history.log`. Git status is clean due to `.gitignore`.
2. Found multiple unit tests using `.teddy/sessions/test` as a hardcoded path.
3. Read the test files - they use `mock_fs` fixture which mocks `IFileSystemManager`, but `SessionService` also uses a repository.
4. MRE confirmed `test_bug_03_prompt_resolution.py` creates the debris; other two test files do not.
5. Targeted probe confirmed `SessionLifecycleManager._handle_planning_and_execution()` creates the debris via `_Tee.__enter__()` which calls `Path.mkdir(parents=True, exist_ok=True)` directly on the real filesystem, bypassing all mocked ports.
6. Confirmed `_Tee.__enter__()` creates the parent directory and opens the file for appending.

## Solution

### Root Cause
The `SessionLifecycleManager._handle_planning_and_execution()` method bypasses the injected `_file_system_manager` port and uses direct `Path` operations via the `_Tee` utility class. The `_Tee.__enter__()` method calls `Path.mkdir(parents=True, exist_ok=True)` and `open()` directly on the real filesystem, meaning even when all ports are mocked in unit tests, the real filesystem is still accessed.

The same pattern exists in `SessionOrchestrator.execute()`, which also creates a `_Tee` with a direct `Path` object.

### Fix
The fix abstracts the Tee/logging behind the `IFileSystemManager` port:

1. **Contract**: Added `open_file_for_append(path: str) -> TextIO` to `IFileSystemManager` port.
2. **Harness**: Implemented `open_file_for_append` in `LocalFileSystemAdapter`.
3. **Seam**: Refactored `Tee.__init__` to accept `TextIO` instead of `Path`.
4. **Logic**: Updated `SessionLifecycleManager._handle_planning_and_execution()` to use the port.
5. **Logic**: Updated `SessionOrchestrator.execute()` to use the port.

### Preventative Measures
To prevent this entire class of "Port Bypass" bugs:
- **Architectural Rule**: All filesystem operations in core services MUST go through the injected `IFileSystemManager` port. Direct `Path.mkdir()`, `open()`, or `Path.write_text()` calls in core services are forbidden.
- **Code Review**: Any new code that creates files or directories in core services must be reviewed for port bypass.
- **Test Harness**: The `_assert_no_test_pollution` fixture in `conftest.py` already snapshots `git status --porcelain` before the suite and asserts no filesystem pollution after all tests complete. This acts as a Poka-Yoke against stray test artifacts.
