# Bug: Windows Path Normalization Regression

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)

## Symptoms
Windows CI reported failing after path normalization changes.

## Context & Scope
### Regressing Delta
- **Commit:** `34719c39` (feat(adapters): implement ls-R style repository tree format)
- **Files:** `src/teddy_executor/adapters/outbound/local_repo_tree_generator.py`, `src/teddy_executor/adapters/outbound/shell_adapter.py` (suspected)
- **Change:** Introduced new tree formatting logic and potentially altered path handling.

## Diagnostic Analysis
### Causal Model
The `_RecursiveListFormatter` uses `Path.relative_to()` and converts it to a string. On Windows, this uses `\` as a separator. The integration tests and the TeDDy protocol expect `/` as a universal path separator for consistency in LLM prompts and reports. This mismatch causes `AssertionError` in Windows CI.

### Discrepancies
- (resolved: Windows CI logs confirm `./a\b:` output) Windows CI fails while macOS/Linux passes.

### Investigation History
- Attempt 1: Failed to fetch logs using hallucinated ID 1234567890.
- Attempt 2: Verified fix on Windows via `debug-windows-fix` branch. `test_tree_integrity_with_deep_unignored_file` passed after path normalization.

## Solution
### Implemented Fixes
- Modified `_RecursiveListFormatter._format_section` in `src/teddy_executor/adapters/outbound/local_repo_tree_generator.py` to explicitly replace `os.sep` with `/` in directory headers.
- Added missing `os` import to `local_repo_tree_generator.py`.

### Prevention
- The fix ensures the `ls-R` tree format maintains a platform-agnostic protocol (forward-slashes only) for cross-platform compatibility.
- Verified via Windows-specific remote CI probe.
