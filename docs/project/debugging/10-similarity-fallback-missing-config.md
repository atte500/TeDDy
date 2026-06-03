# Bug: Hardcoded Similarity Fallback Failure with Missing Config
- **Status:** Resolved
- **Milestone:** [Milestone 2: Stability & Infrastructure](/docs/project/milestones/02-stability-and-polish.md)
- **Vertical Slice:** [Slice: 02-06-Orchestrator Hardening](/docs/project/slices/02-06-orchestrator-hardening.md)
- **Specs:** [Stability & Bug Fixes Spec](/docs/project/specs/stability-and-bugfixes.md)

## Symptoms
**Expected:** When `config.yaml` is missing, the `ActionFactory` injects a hardcoded default similarity threshold (0.95) and the EDIT action succeeds.
**Actual:** The EDIT action logs SUCCESS at the dispatcher level, but the `ExecutionOrchestrator` returns `RunStatus.FAILURE` as the overall plan status.
**Minimal Reproduction:** Execute any plan with an EDIT action using a `YamlConfigAdapter` pointed at a non-existent file. The test `test_edit_action_uses_hardcoded_similarity_fallback_when_config_is_missing` reproduces this.

## Context & Scope
### Regressing Delta
Commit `106287e2 feat(executor): implement mid-execution EDIT consistency with hash tracking` introduced `_compute_file_hash` and `_file_hashes` to `ActionExecutor`. The pre-dispatch hash check calls `self._file_system_manager.read_file(path)`. The `IFileSystemManager` port defines two read methods: `read_file` and `read_raw_file`. The test's mock (`mock_fs`, a POSIXPathMock specced on `IFileSystemManager`) only configures `read_raw_file.return_value = "original content"`, leaving `read_file` unconfigured, which returns `None` (or raises).

### Environmental Triggers
Requires a `YamlConfigAdapter` pointing to a non-existent config file and an `ActionExecutor` with hash tracking enabled.

### Ruled Out
- The similarity threshold injection in `ActionFactory._handle_edit_protocol` is working correctly (the edit action succeeds at the dispatcher level).
- The `YamlConfigAdapter` fallback behavior for non-existent files returns `{}` which is correct.

## Diagnostic Analysis
### Causal Model
The `ActionExecutor.confirm_and_dispatch` method, after the hash tracking commit, performs a pre-dispatch hash check for EDIT actions: it calls `_compute_file_hash(path)` which reads the file via `self._file_system_manager.read_file(path)`, encodes to UTF-8, and SHA256 hashes it. If `read_file` returns `None` (because the mock only configures `read_raw_file`), the `.encode("utf-8")` call raises a `TypeError: 'NoneType' object has no attribute 'encode'`. This exception is caught by the orchestrator's general exception handler (not by the `except OSError` block in `confirm_and_dispatch`), causing the overall plan status to be FAILURE. The dispatcher-level log still shows SUCCESS because the exception occurs AFTER the dispatcher returns its ActionLog but BEFORE the success path is finalized (or the exception happens within `confirm_and_dispatch` itself, aborting the happy path and returning a FAILURE ActionLog via the `enrich_failed_log` or a fallback).

### Discrepancies
- The captured stderr shows "EDIT" then "SUCCESS", suggesting the dispatcher returned SUCCESS, but the orchestrator recorded FAILURE. This could be because the `confirm_and_dispatch` returns a FAILURE ActionLog after the hash check raises, and the orchestrator correctly tallies that as a failure. The stderr "SUCCESS" comes from a different log statement inside `action_dispatcher.py` that fires before the hash check. (*Unresolved*)

### Investigation History
1. Hash Tracking Regression Hypothesis. The `_compute_file_hash` call in `confirm_and_dispatch` for EDIT actions expects `read_file` to return a string. The test mock only defines `read_raw_file`, causing a `TypeError`. Pending verification.

## Solution
### Root Cause
Commit `106287e2` added hash tracking (`_compute_file_hash`) in `ActionExecutor.confirm_and_dispatch` that calls `IFileSystemManager.read_file(path)` post-dispatch for EDIT actions. The integration test `test_edit_action_uses_hardcoded_similarity_fallback_when_config_is_missing` configured `mock_fs.read_raw_file` but not `mock_fs.read_file`, causing `read_file` to return a `MagicMock` instance. When `_compute_file_hash` tries `hashlib.sha256(content.encode("utf-8"))`, the `MagicMock.encode()` returns another MagicMock, raising `TypeError: object supporting the buffer API required`. This `TypeError` is not caught by the `except OSError` handler and propagates to the `ExecutionOrchestrator`'s generic exception handler, resulting in `RunStatus.FAILURE`.

### Fix
Add `mock_fs.read_file.return_value = "original content"` to the failing test. This ensures the hash tracking logic receives a real string instead of a MagicMock.

### Preventative Measures (Categorical Audit)
A `git grep` across `tests/suites/` found **5 files** where `read_raw_file.return_value` is set but `read_file.return_value` is **not** set. Of these, only `test_config_defaults.py` is currently failing. The other 4 files (`test_validator_edit_resilience.py`, `test_validator_edit.py`, `test_validator_edit_performance.py`, `test_console_plan_reviewer.py`) do not exercise the `ActionExecutor.confirm_and_dispatch` path and are not affected, but represent a latent class of mock asymmetry. To systematically prevent this class of regression, the project should adopt a convention: **any mock that configures `read_raw_file` MUST also configure `read_file`** since both are part of the same port contract. Alternatively, a harness-level check could be introduced to verify symmetrical mock configuration.
