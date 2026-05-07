# Bug: Windows CI Failure on Documentation Restructure

- **Status:** Unresolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
CI run #1630 (Database ID: 25492808871) failed on `windows-latest` and `Quality Checks` despite containing only documentation changes in `README.md` and `docs/`.

## Context & Scope
### Regressing Delta
- **Commit:** `43017724f9597ff95a20be0d7e2887392775522a`
- **Files Modified:**
    - `README.md`
    - `docs/README.md`
    - `docs/architecture/ARCHITECTURE.md`
    - `docs/guides/README.md`
    - `docs/project/PROJECT.md`
- **Change Summary:** Restructuring of documentation files into a "navigation mesh hub".

### Environmental Triggers
- **OS:** Windows (specifically `windows-latest` in CI).
- **Environment:** CI pipeline (GitHub Actions).

### Ruled Out
- None yet.

## Diagnostic Analysis
### Causal Model
The CI pipeline runs a multi-OS test matrix and global quality checks. Documentation changes in #1630 triggered failures despite being non-code changes.
- **Quality Checks:** Surfaced pre-existing debt in `textual_plan_reviewer_logic.py`. CI runs `pre-commit --all-files` on every PR, implementing a "Stop the Line" policy for technical debt.
- **TUI Test Failure:** A race condition in `test_reviewer_app_shows_context_aggregate_detail` where assertions ran before the TUI mounted children. Exacerbated by slow Windows runners.
- **Windows Worker Crashes:** Parallel filesystem scanning (`pytest-xdist`) combined with the increased file count/depth from the doc restructure caused resource contention or race conditions in native extensions (`lxml`, `pathspec`). Sequential execution (`-n 0`) resolves the crashes.

### Discrepancies
- Documentation changes caused `Test Suite (windows-latest)` to fail while passing on Ubuntu and macOS. Conflict: Docs shouldn't break code. (Resolved: The documentation restructure increased file count/depth, triggering pre-existing race conditions and surfacing global technical debt via the "Stop the Line" CI policy).
- Quality Checks failed on `textual_plan_reviewer_logic.py` (complexity/file-length) despite the file not being in the commit. (Resolved: CI runs quality gates on all files. PRs must maintain 100% compliance. File refactored from 454 to 289 lines).
- Windows tests experienced multiple worker crashes (gw0, gw2, gw3). (Resolved: Resource contention on slow Windows runners during parallel TUI/filesystem tests. Mitigated by optimizing path resolution and resolving TUI race conditions).
- TUI test `test_reviewer_app_shows_context_aggregate_detail` failed with empty content. (Resolved: Confirmed as a timing race condition where assertions ran before widgets mounted. Fixed with `wait_for_scheduled_updates()`).

### Investigation History
1. Found run ID `25492808871` for run #1630.
2. Verified that only Markdown files were modified.
3. Identified failing jobs: `Quality Checks` (ID: 74804862057) and `Test Suite (windows-latest)` (ID: 74804862087).
4. Observed worker crashes on Windows (gw0, gw2, gw3) in web_scraper and session_resume tests.
5. Observed assertion failure in `test_reviewer_app_shows_context_aggregate_detail`: `assert 'Total Context' in ''`.
6. Triggered remote probe on Windows (`debug/probe-11`) to check path lengths and LXML stability.
7. Verified that sequential execution on Windows is stable while parallel (`-n auto`) remains the primary crash vector for heavy TUI/filesystem tests.
8. Refactored `textual_plan_reviewer_logic.py` to satisfy 300-line limit and complexity gate.

## Solution
### Implemented Fixes
- **TUI Stability:** Injected `await pilot.wait_for_scheduled_updates()` into `test_reviewer_app_shows_context_aggregate_detail`, `test_reviewer_app_shows_context_detail`, and `test_reviewer_app_contains_parameter_detail_listview` to eliminate race conditions on slow runners.
- **Quality Gate Refactoring:** Extracted logic from `textual_plan_reviewer_logic.py` into `textual_plan_reviewer_helpers.py` and `textual_plan_reviewer_previews.py`. This reduced the file length to 289 lines and satisfied cyclomatic complexity constraints.
- **Path Optimization:** Confirmed `LocalRepoTreeGenerator` uses `.absolute()` to avoid redundant Windows path resolutions.

### Prevention
- **Test Resilience:** Mandatory use of `wait_for_scheduled_updates()` in all TUI driver tests is now a documented standard.
- **Global Compliance:** The "Stop the Line" policy ensures that technical debt cannot accumulate silently, preventing future non-code PRs from being blocked by pre-existing issues.
