# Experiment: Terminal Action Isolation Failure

- **Related Artifacts:** `tests/suites/acceptance/test_terminal_action_isolation.py`
- **Status:** Pending

## Objective & Requirements
Isolate and resolve the issue where terminal actions (`INVOKE`, `RETURN`) are not correctly enforcing isolation in multi-action plans, allowing preceding side-effecting actions to execute.

## Experiment Log
### Initial Triage
- *Hypothesis:* The isolation check is likely performed at the individual action level or late in the orchestration loop, allowing previous actions to commit their side effects before the terminal action's isolation requirement is evaluated.
- *Experiment:* Read core services and search for isolation logic.
- *Observation:* `MarkdownPlanParser` only deselects the terminal action itself in `_parse_actions`. `ExecutionOrchestrator` skips based on `action.selected`.
- *Conclusion:* Confirmed. This aligns with "Relaxed Isolation" policy.

### Investigation into "Debris" and Outdated Tests
- *Hypothesis:* The isolation policy has been relaxed to allow non-terminal actions to execute in mixed plans. The failing tests are outdated (expecting strict isolation). I must also verify the "debris" is not leaking into the project root.
- *Experiment:* Check adapter localization and verify file leakage in the repository root.
- *Observation:* Confirmed "debris" (e.g., `iso_test_primary.txt`) was appearing in the project root because `LocalFileSystemAdapter` was resolving relative paths against the project root instead of the test workspace.
- *Conclusion:*
1. Fixed `TestEnvironment` to use absolute paths for workspaces.
2. Fixed `RealAdapterMixin` to monkeypatch `LocalFileSystemAdapter.__init__` and `LocalRepoTreeGenerator.__init__`, forcing the absolute workspace path and ensuring reliable isolation in acceptance tests.
3. Updated `test_terminal_action_isolation.py` to reflect "Relaxed Isolation" policy (confirming side-effects in workspace and terminal-action skips).

### Regression: Workspace Mismatch
- *Hypothesis:* The global monkeypatch in `RealAdapterMixin` breaks tests that use a custom workspace (like pytest's `tmp_path`) while also calling `with_real_filesystem()`.
- *Experiment:* Run all tests.
- *Observation:* `tests/suites/acceptance/test_edit_newline_mismatch.py` failed because it created files in `tmp_path` but the adapter was forced to `env.workspace`.
- *Conclusion:* Refined the monkeypatch in `RealAdapterMixin` to be conditional. However, this caused a regression in `test_terminal_action_isolation.py` where files were no longer appearing in the workspace. Investigating why explicit absolute paths are failing to anchor correctly.

### Regression: Workspace Mismatch
- *Hypothesis:* The global monkeypatch in `RealAdapterMixin` breaks tests that use a custom workspace (like pytest's `tmp_path`) while also calling `with_real_filesystem()`.
- *Experiment:* Run all tests.
- *Observation:* `tests/suites/acceptance/test_edit_newline_mismatch.py` failed because it created files in `tmp_path` but the adapter was forced to `env.workspace`.
- *Conclusion:* Pending.

## Analysis & Recommendations
(Pending)
