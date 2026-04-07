# MRE: Terminal Action Isolation Failure

- **Status:** Resolved

## Failure Context
The acceptance tests for terminal action isolation are failing because the side-effecting `CREATE` action reports `SUCCESS`, but the file is not found in the `real_env.workspace`.

## Steps to Reproduce
1. Run `pytest tests/suites/acceptance/test_terminal_action_isolation.py`

## Expected vs. Actual Behavior
- **Expected:** `CREATE` action writes to the temporary workspace path provided by `real_env`.
- **Actual:** `CREATE` action reports `SUCCESS` but file is missing from workspace.

## Relevant Code
- `src/teddy_executor/adapters/outbound/local_file_system_adapter.py`
- `tests/harness/setup/real_adapter_mixin.py`
- `tests/harness/setup/test_environment.py`

## Investigation Log
> **Hypothesis**: The `LocalFileSystemAdapter` is not correctly anchored to the `real_env.workspace`.
> **Experiment**: Run failing test with `-n 0 -s` and search for the unique filename.
> **Observation**: Test failed. `[LOUD DEBUG]` prints from the real adapter were missing. No file was found on disk.
> **Conclusion**: The system is using the `POSIXPathMock` registered in `TestEnvironment.setup` instead of the real adapter. The `SUCCESS` report is a false positive from the mock.

> **Hypothesis**: `punq` does not replace an `instance` registration with a subsequent class registration.
> **Experiment**: Create a spike to test `punq` registration shadowing.
> **Observation**: Spike `spikes/debug/test_punq_behavior.py` showed that `punq` DOES replace registrations correctly.
> **Conclusion**: The issue is not in `punq`'s basic registration mechanism.

> **Hypothesis**: Action handlers are bound to the mock FS manager during their initial registration and do not refresh when `IFileSystemManager` is re-registered.
> **Experiment**: Examine `ActionFactory` and registration modules.
> **Observation**: `ActionFactory` resolves `IFileSystemManager` from the container on every `create_action` call. `LocalFileSystemAdapter` has a `[LOUD DEBUG]` print that is missing from test output.
> **Conclusion**: The system is resolving the Mock FS instead of the Real FS. This is likely because `with_real_filesystem()` was never called.

> **Hypothesis**: The `real_env` fixture does not activate the real filesystem by default.
> **Experiment**: Locate and examine the `real_env` fixture definition.
> **Observation**: Found in `tests/harness/setup/composition.py`. It calls `with_real_filesystem()`.
> **Conclusion**: The fixture IS attempting to use real adapters, but they aren't being used by the CLI.

> **Hypothesis**: `punq` registration shadowing and CLI bootstrap interference.
> **Experiment**: Create a spike to test `punq` registration order and examine `__main__.py`.
> **Observation**: Spike `spikes/debug/verify_container_singleton.py` confirmed that `punq` ignores subsequent registrations for a key once an `instance` is registered. `__main__.py` revealed a `bootstrap()` callback that re-registers the FS adapter using the project root before every command.
> **Conclusion**: The Mock FS instance registered in `TestEnvironment.setup` shadows the Real FS adapter registration. Furthermore, the CLI's `bootstrap` logic stomps over any test-specific registration.

## Root Cause Analysis
1. **punq Registration Behavior**: The `punq` DI container does not support implementation swapping for a key once an `instance` (singleton) registration exists. `TestEnvironment` registers the Mock FS as an instance in its `setup` method, which silently causes all subsequent `register` calls for `IFileSystemManager` to be ignored.
2. **CLI Bootstrap Stomping**: The `bootstrap()` callback in `teddy_executor/__main__.py` is a `typer` callback that executes before every command. It re-registers `IFileSystemManager` with a `LocalFileSystemAdapter` anchored to the project root (discovered via `find_project_root()`). This overwrites any test-specific registration, redirecting all file operations back to the real project directory instead of the test's temporary workspace.

## Proposed Fix
| Strategy | Implementation | Pros | Cons |
| :--- | :--- | :--- | :--- |
| **Deep Swap (Harness)** | `TestEnvironment` creates a fresh `punq.Container` and re-patches `teddy_executor.container.get_container` when implementation swaps occur. | Bypasses `punq` shadowing; ensures clean state. | Requires re-patching. |
| **Defensive Bootstrap (CLI)** | Wrap registrations in `if IFileSystemManager not in c.registrations:` in `__main__.py`. | Prevents test workspace stomping. | Relies on `punq` internals. |

## Implementation Notes
- Updated `__main__.py` with `is_override` check using `punq` internal registry to allow overwriting transients (defaults) but protecting singletons (mocks/overrides).
- Updated `RealAdapterMixin` to use `Scope.singleton` for anchored adapters.
- Harmonized `test_edit_newline_mismatch.py` to use `env.workspace`.

## Final Root Cause Analysis
1. **punq Registration Behavior**: The `punq` DI container does not support implementation swapping for a key once an `instance` registration exists.
2. **CLI Bootstrap Stomping**: The `bootstrap()` callback was overwriting test-specific registrations.
3. **Guard Over-Correction**: The initial fix used a broad guard that prevented project-root anchoring in normal operation.
4. **Surgical Guard**: The final fix uses a scope-aware guard in `bootstrap()` that allows overwriting transient (default) registrations while respecting singletons (mocks/overrides).
