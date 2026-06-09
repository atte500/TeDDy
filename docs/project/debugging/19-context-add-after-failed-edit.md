# Bug: File Not Added to turn.context After Failed EDIT
- **Status:** Resolved
- **Milestone:** [02-stability-and-polish](/docs/project/milestones/02-stability-and-polish.md)
- **Vertical Slice:** [N/A]
- **Specs:** [Stability & Bug Fixes](/docs/project/specs/stability-and-bugfixes.md)

## Symptoms
When an EDIT action fails (e.g., FIND block does not match), the target file path is NOT added to the next turn's `turn.context`. Expected behavior per the Turn Transition Algorithm: "For each READ, CREATE, and EDIT action, add its resource/file path to T_next/turn.context (provided the file exists)." The spec does not condition this on action success, so even failed EDIT actions should add the file to context.

## Context & Scope
### Regressing Delta
The auto-add to context feature was implemented as part of Slice 02-04 (Context Automation). The condition that filters by action success is the likely regression.

### Environmental Triggers
Any failed EDIT action will fail to add its file to turn.context.

### Ruled Out
- Not related to session execution logic.
- Not related to the model display bug previously investigated.

## Diagnostic Analysis
### Causal Model
The auto-addition of file paths to `turn.context` is implemented in `SessionService._apply_execution_effects()` in `transition_to_next_turn()`. Two bugs were fixed:
1. **Bug 16 (Validation Failure):** The plan fails validation; `action_logs` empty but `original_actions` populated. Fix: `_apply_original_actions_effects` fallback.
2. **Bug 19 (Execution Failure):** The `_apply_execution_effects` filtered out FAILURE-status actions. Fix: Allow FAILURE-status EDIT actions to contribute paths.

**However, both fixes rely on key-name lookups that do not match real execution.** The plan parser converts `- **File Path:**` to internal key `"path"` via `link_key_map={"File Path": "path"}` (`action_parser_strategies.py:30`). The `ActionDispatcher` copies `action.params` directly into `ActionLog.params` (`action_dispatcher.py:52`). Therefore, real ActionLogs have `"path"` as the key, NOT `"File Path"` or `"file_path"`.

The extraction methods `_apply_execution_effects` and `_apply_original_actions_effects` only check for `"file_path"` or `"File Path"`. They **never** check for `"path"`. This means:
- For runtime execution failures (mismatching FIND blocks), the `"path"` key is never found.
- The `resource_val` is `None`, so the file path is never added to `turn.context`.
- The Bug 19 fix (allowing FAILURE-status) is correct in logic, but the key lookup still prevents it from working in production.

**The unit test creates a false positive** by using `"File Path"` key instead of the real `"path"` key.

### Discrepancies
1. Validation failure reports have empty `action_logs`. The `_apply_execution_effects` adds nothing, while `original_actions` is populated. (Resolved: Bug 16 fix added `_apply_original_actions_effects` fallback.)
2. Execution failure reports have `action_logs` with FAILURE status. The `_apply_execution_effects` skips non-SUCCESS entries, so no path is added. (Resolved: Bug 19 fix changed filter to allow FAILURE-status EDIT actions to contribute paths.)
3. **Key-name mismatch**: The unit test creates mock `ActionLog` objects with `"File Path"` key (CamelCase with space), but real execution produces `"path"` key. This is because the plan parser uses `link_key_map={"File Path": "path"}` (`action_parser_strategies.py:30`) and `ActionDispatcher` copies `action.params` directly into `ActionLog.params` (`action_dispatcher.py:52`). The extraction methods `_apply_execution_effects` and `_apply_original_actions_effects` only check for `"file_path"` and `"File Path"`, **never for `"path"`**. Therefore, the Bug 19 fix (allowing FAILURE-status EDIT actions) never activates in production for real runtime failures because the key lookup returns `None` and the file path is silently dropped. The unit test passes because it uses the wrong key, creating a false positive. **(Core root cause of the persistent user-reported bug.)**

### Investigation History
1. **Trace auto-add to context code.** Found `SessionService._apply_execution_effects()` iterates over `action_logs` and only adds for SUCCESS status. Conclusion: This is the central auto-addition method.
2. **Review Bug 16 findings.** Bug 16 identified validation failure gap (empty `action_logs` with populated `original_actions`). Fix applied: `_apply_original_actions_effects` fallback. Conclusion: Bug 16 resolved validation failure path.
3. **Identify execution failure gap.** Re-analysis of `_apply_execution_effects` reveals FAILURE status actions are skipped. The spec does not condition addition on success. Conclusion: Execution failures (runtime EDIT failures) are a likely remaining source of the user-reported bug.
4. **Probe real ActionLog param keys.** Found `action_parser_strategies.py:30` uses `link_key_map={"File Path": "path"}`. `ActionDispatcher:52` copies `action.params` directly. Therefore real ActionLogs have `"path"` key, but extraction methods check for `"file_path"`/`"File Path"`. Probe executed at `spikes/debug/19-probe-apply-execution-effects.py` confirmed: real key `"path"` is never found, so Bug 19 fix never activates in production.
5. **Shadow file verification.** Created `spikes/debug/shadow_session_service.py` with fix adding `"path"` key lookup. (Verified: shadow fix correctly extracts path from real ActionLogs.)

## Solution
### Root Cause
There are two interacting issues:
1. **Logic Fix (Bug 19):** The `_apply_execution_effects` filtered out FAILURE-status actions. Fixed by allowing FAILURE-status EDIT actions to contribute paths.
2. **Key-Name Mismatch (This Fix):** The plan parser maps `"File Path"` to internal key `"path"` via `link_key_map`. The `ActionDispatcher` copies `action.params` directly. But the extraction methods only check for `"file_path"` and `"File Path"`, never for `"path"`. So the Bug 19 fix never activated in production.

### Implementation
1. Added `"path"` as a fallback key in both `_apply_execution_effects()` and `_apply_original_actions_effects()` in `session_service.py`:
   - `resource_val = log.params.get("file_path") or log.params.get("File Path") or log.params.get("path")`
2. Updated the regression test (`test_bug_19_execution_failure_context.py`) to use the real-world key `"path"` instead of `"File Path"` to prevent false positives.
3. **Systemic fix:** Also updated `validation_rules/edit.py` to check for `"path"` key in addition to `"file_path"` and `"File Path"`.
4. Verification: All 5 Bug 19 regression tests pass. Broader session service tests (21 tests) pass. Validated edit tests pass.

### Preventative Measures
- When extracting parameters from plan-parsed data, always consult the actual parser mapping (`action_parser_strategies.py`) to determine the real key names.
- Integration tests should use the real parser pipeline to ensure end-to-end key consistency.
- Any future extraction methods must check both the human-readable key (with spaces/CamelCase) and the internal normalized key.
- Grep for `params.get("File Path")` patterns to find all locations that need the `"path"` fallback.
