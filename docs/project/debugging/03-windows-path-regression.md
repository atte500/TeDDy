# Bug: Windows Path Normalization Regression

- **Status:** Unresolved
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
