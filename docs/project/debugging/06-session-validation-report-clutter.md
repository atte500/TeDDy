# Bug: Redundant Resource Contents in Session Validation Reports

- **Status:** Resolved
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Vertical Slice:** [docs/project/slices/02-06-orchestrator-hardening.md](/docs/project/slices/02-06-orchestrator-hardening.md)
- **Specs:** [docs/project/specs/stability-and-bugfixes.md](/docs/project/specs/stability-and-bugfixes.md)

## Symptoms
In session mode, when a plan fails validation (e.g., an `EDIT` mismatch), the resulting report incorrectly includes a "Resource Contents" section containing the full file content.

**Expected Behavior:** The "Resource Contents" section should be suppressed in session mode (as the content is already in `input.md`), but the "Closest Match Diff" (which is part of the error message string) should be preserved.

## Context & Scope
### Regressing Delta
The `is_session` flag is correctly detected in `SessionOrchestrator.execute` but is not passed to:
1.  `SessionReplanner.build_failure_report`
2.  `SessionLifecycleManager.trigger_replan`

Additionally, `SessionReplanner.gather_failed_resources` gathers full file content even when in session mode, leading to unnecessary I/O.

### Ruled Out
- **Template Logic:** `execution_report.md.j2` has been verified via spike to correctly suppress the section if `is_session` is `True`.

## Diagnostic Analysis

### Causal Model (Verified)
1.   detects  via .
2.   returns logical errors.
3.   calls:
    -  — no  param, performs unnecessary I/O.
    -  — no  param.
4.   internally calls  — no  param.
5.   constructs  with  (default).
6.  The report template renders "Resource Contents" because  is .

### Discrepancies (All Resolved)
-  does not accept . (resolved: Shadow fix adds  and forwards it to .)
-  does not accept  and performs unnecessary I/O in session mode. (resolved: Shadow fix adds  and returns  if .)
-  does not accept . (resolved: Fix adds  parameter and passes it downstream.)
-  does not pass  flag. (resolved: Fix passes  variable from the execute method.)

### Investigation History
1. **Hypothesis:**  flag is lost during validation failure path. **Observation:** Code review confirms  calls  and  without . **Conclusion:** Valid — delta isolated.
2. **Hypothesis:** Template logic is broken. **Observation:** Spike verifies template suppresses "Resource Contents" when . **Conclusion:** Ruled out.
3. **Hypothesis:** MRE can reproduce missing . **Observation:** MRE in  confirms  (exit code 1). **Conclusion:** Bug reproduced.
4. **Hypothesis:** Shadow fix propagates  correctly. **Observation:** Shadow verification script passes all 4 tests (exit code 0).  propagates ;  skips I/O when ; defaults preserved. **Conclusion:** Fix validated.

## Solution

### Root Cause
The  flag detected by  was not propagated through the validation failure path:
-  did not accept , so  defaulted to .
-  performed unnecessary I/O in session mode.
-  did not accept .

### Proven Fix (Verified via Shadow File)
1. ****: Added  parameter; forwards it to  constructor.
2. ****: Added ; returns  immediately if  (skips I/O).
3. ****: Added  parameter; passes it to  and .
4. ****: Passes the detected  flag to both  and .

### Systemic Preventative Measures
- **Category: Dropped Context Flag** — When a parent method detects a boolean flag affecting downstream behavior, all callees must accept and forward that flag. This bug is a classic example of failure to propagate context through a call chain.
- **Pattern to enforce:** Any new boolean parameter added to a workflow method must be traced through all call paths to ensure no gaps. Use static analysis (e.g., mypy strict optional checks) to catch signature mismatches proactively.
