# Windows Path Normalization Mismatch in Unit Tests

Metadata Header:
- **Status:** Resolved
- **MRE:** N/A (Remote CI Failure: [test(unit): fix platform-specific path separators and formatting #977](https://github.com/atte500/TeDDy/actions/runs/12345))

## 1. Summary
Unit tests in the Core Services (`InitService`, `PlanningService`, `SessionService`) consistently fail on Windows environments. These failures manifest as `AssertionError` during `unittest.mock` verification of the `IFileSystemManager` outbound port. The system incorrectly reports that an expected call with a platform-native path (using backslashes `\`) was not found, while the actual call used the project's "Internal POSIX" convention (using forward slashes `/`).

## 2. Investigation Summary
1.  **Context Gathering:** Reviewed CI logs and identified failures in `test_init_service.py`, `test_planning_service_logging.py`, and `test_session_service_transition.py`.
2.  **Static Analysis:** Audited production services and confirmed that path construction predominantly uses literal forward slashes or `.as_posix()` calls to enforce a platform-agnostic internal representation.
3.  **Experimental Verification:** Created a spike on a Windows environment (simulated) confirming that `str(Path("a/b"))` returns `"a\b"`, which causes `mock.assert_called_with("a/b")` to fail due to strict string comparison.
4.  **Robust Fix Spike:** Verified that a custom `MagicMock` subclass can normalize the primary path argument of any call or assertion, allowing native OS paths in tests to match POSIX paths in production code seamlessly.

## 3. Root Cause
-   **Technical Cause:** The `unittest.mock` library performs strict string equality for call assertions. The Core Services follow a "Internal POSIX" convention where all paths are normalized to forward slashes before interacting with ports. However, the unit tests use `str(Path(...))` to construct expectations, which returns platform-native backslashes on Windows, creating a string mismatch.
-   **Systemic Cause:** The Test Harness (`TestEnvironment`) provided a standard `Mock` for the filesystem which did not enforce or account for the project's path normalization rules. This placed the burden of normalization on every individual test author, leading to inconsistent setup and cross-platform fragility.

## 4. Verified Solution
Implement a specialized `POSIXPathMock` class within `tests/harness/setup/test_environment.py`. This class overrides `__call__` and the standard `assert_*` methods to automatically normalize the first string argument (the path) to use forward slashes.

```python
import unittest.mock as mock

class POSIXPathMock(mock.MagicMock):
    def _normalize_args(self, args, kwargs):
        new_args = list(args)
        if new_args and isinstance(new_args[0], str):
            new_args[0] = new_args[0].replace("\\", "/")
        return tuple(new_args), kwargs

    def __call__(self, /, *args, **kwargs):
        new_args, new_kwargs = self._normalize_args(args, kwargs)
        return super().__call__(*new_args, **new_kwargs)

    def assert_called_with(self, /, *args, **kwargs):
        new_args, new_kwargs = self._normalize_args(args, kwargs)
        return super().assert_called_with(*new_args, **new_kwargs)
    # ... (other assert methods)
```

## 5. Preventative Measures
1.  **Harness-Level Enforcement:** By baking normalization into the `mock_fs` in `TestEnvironment`, all future unit tests will be "Safe by Default" for Windows.
2.  **CI Parity:** Maintain the Windows/macOS runners in the CI pipeline to ensure that architectural assumptions (like Internal POSIX) are verified against platform realities on every push.
3.  **Adapter Responsibility:** The `LocalFileSystemAdapter` remains responsible for translating the Internal POSIX paths back to native OS paths before calling the actual `pathlib` or `os` modules. This ensures the Core remains truly decoupled.

## 6. Implementation Notes
The `POSIXPathMock` was implemented as a subclass of `MagicMock` and integrated into `tests/harness/setup/test_environment.py`.

Key Features:
- **Child Mock Persistence:** Overrides `_get_child_mock` to ensure all methods (e.g., `mock_fs.read_file`) are also `POSIXPathMock` instances.
- **Normalization Strategy:** Intercepts the first argument if it's a string and replaces all backslashes (`\`) with forward slashes (`/`).
- **Assertion Coverage:** Overrides `assert_called_with`, `assert_any_call`, `assert_called_once_with`, and `assert_has_calls` to ensure test expectations are normalized before comparison.

The `TestEnvironment._register_default_mocks` method now uses `POSIXPathMock(spec=IFileSystemManager)` for the filesystem port. A new regression test `test_filesystem_mock_normalizes_paths_systemically` was added to `tests/suites/unit/test_environment_harness.py` to protect this fix.
