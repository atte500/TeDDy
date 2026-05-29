# Bug: Ambiguous EDIT validation gap

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

An `EDIT` action passes pre-flight validation but fails during execution with an "ambiguous occurrences" error.

### Actual Behavior (Execution Report snippet)
```
### EDIT: [session_cli_handlers.py](/src/teddy_executor/adapters/inbound/session_cli_handlers.py)
- Status: FAILURE
- Details: Found 2 ambiguous occurrences of '...'. Aborting edit to prevent ambiguity.
```

### Expected Behavior
The ambiguity should be caught during the `PlanValidator` phase, preventing the execution from starting and providing early feedback to the user.

## Context & Scope

### Regressing Delta
Unknown. This is a systemic divergence between the validation and execution paths for `EDIT` actions.

### Environmental Triggers
- **Large Files**: Files exceeding `read.max_lines` (default 1000) where ambiguity exists beyond the truncation point.
- **Fuzzy Duplicates**: Files containing multiple blocks that share the same high similarity score relative to a provided `FIND` block.

### Ruled Out
- **Path Safety**: Correctly validated by `validate_path_is_safe`.
- **File Existence**: Correctly validated by `path_exists`.

## Diagnostic Analysis

### Causal Model
The system exhibits an "Ambiguity Gap" due to two verified mechanisms:

1. **Mechanism A: Systemic Truncation Divergence (Large Files)**:
    - `EditActionValidator` uses `IFileSystemManager.read_file()`, which truncates content to 1000 lines.
    - `LocalFileSystemAdapter.edit_file()` reads the raw text via `Path.read_text()`.
    - Duplicates located beyond the 1000-line threshold are invisible to the validator but trigger ambiguity failures in the executor.

2. **Mechanism B: Heuristic Threshold Sensitivity (All Files)**:
    - The `gather_candidate_starts` heuristic uses the provided `threshold` as a pre-filter.
    - If `EditActionValidator` uses a higher threshold (e.g., 1.00 from `config.yaml`) than the execution path (which may fall back to `DEFAULT_SIMILARITY_THRESHOLD=0.95` if not properly injected), the validator's heuristic phase will filter out near-matches that the executor's phase will gather.
    - If two such near-matches exist, the validator sees 0 matches (yielding a "Not Found" error or a false "Unique Match" if one is perfect) while the executor sees 2+ matches (yielding an "Ambiguity" error).

### Discrepancies
- `EditActionValidator` uses truncated view; `EditSimulator` uses full view. Conflict: Resolution of ambiguity is inconsistent on large files. (resolved: Confirmed via code audit of `LocalFileSystemAdapter.read_file` vs `edit_file` and verified via MRE `spikes/debug/01-ambiguous-edit-mre.py`).
- `EditActionValidator` and Execution path might use different thresholds. Conflict: Heuristic filtering in `gather_candidate_starts` is threshold-sensitive. (resolved: Confirmed via code audit of `EditActionValidator` and `ActionChangesetBuilder` and verified via MRE `spikes/debug/02-tie-score-ambiguity-mre.py`).

### Investigation History
1. **Initial discovery**: User report showing execution failure for ambiguity in `session_cli_handlers.py`.
2. **Reproduction (Truncation)**: Created MRE `spikes/debug/01-ambiguous-edit-mre.py`. Verified that forcing a low `max_read_lines` (e.g. 5) causes `PlanValidator` to miss an ambiguity that exists further down the file, while `EditSimulator` correctly identifies and fails on it.
3. **Threshold Divergence Analysis**: Created MRE `spikes/debug/02-tie-score-ambiguity-mre.py`. Proved that if the validator uses 0.98 and executor uses 0.95, a search for a 0.96-similar block will be ignored by the validator but cause ambiguity in the executor.
4. **Code Audit**: Confirmed `LocalFileSystemAdapter.read_file` truncates while `edit_file` reads raw text. Confirmed `EditActionValidator` and `ActionChangesetBuilder` independently resolve the similarity threshold from config.

## Solution

### Root Cause
The system exhibited an "Ambiguity Gap" where ambiguities in `EDIT` actions were missed during pre-flight validation but triggered failures during execution. This was caused by two primary factors:
1.  **Systemic Truncation Divergence**: `EditActionValidator` relied on `IFileSystemManager.read_file()`, which truncates content to 1000 lines for human-centric CLI display. Execution-path components like `EditSimulator` used raw text access. This made duplicates located past the truncation threshold invisible to the validator.
2.  **Dispersed Threshold Resolution**: Similarity thresholds were independently resolved from configuration in multiple services (`EditActionValidator` and `ActionChangeSetBuilder`), leading to potential mismatches in how "matches" and "ambiguities" were identified.

### Proven Fix
1.  **Character-Perfect Access**: Added `read_raw_file()` to the `IFileSystemManager` port and implemented it in `LocalFileSystemAdapter`. This ensures all machine-logic (validation, simulation, changeset building) operates on the full, untruncated file content.
2.  **Centralized Threshold Resolution**: Created a shared `resolve_similarity_threshold` helper in `src/teddy_executor/core/services/validation_rules/helpers.py`. Both `EditActionValidator` and `ActionChangeSetBuilder` now use this helper to ensure identical resolution of similarity parameters from action overrides and global configuration.

### Preventative Measures
- **Machine vs. Human Ports**: Established a strict architectural distinction between human-centric (truncated) and machine-logic (raw) file access ports.
- **Contract-Driven Consistency**: Centralized logic that influences cross-boundary behavioral consistency (like threshold resolution) into shared service helpers to prevent logic drift between validation and execution paths.
