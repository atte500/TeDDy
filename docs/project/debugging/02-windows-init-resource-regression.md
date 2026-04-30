# Bug: Windows CI Regression: InitService Resource Resolution

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
CI failure on `main` branch (run 25157116659). Note: Manual probe of the full test suite on Windows-latest passed on a debug branch, suggesting the failure lies in the `quality-checks` job rather than the `test-suite`.

## Context & Scope
### Regressing Delta
Commit `327381d4d01a8a3e0633a01f8794ea640fa4af3c` ("feat(config): implement centralized configuration baseline") replaced relative path joining with `importlib.resources.files` and manual `str()` conversion/`os.path.abspath` in `InitService`.

### Environmental Triggers
- OS: Windows (CI)
- Component: `InitService`

### Ruled Out
- `MarkdownReportFormatter` (Previous fix confirmed in 01-windows-template-path-regression.md)

## Diagnostic Analysis
### Causal Model
`InitService` uses `importlib.resources.files` but then converts it to a string and uses `os.path.abspath` and `os.path.join`. This manual path manipulation of package resources is likely failing on Windows CI environments where paths might be UNC or have different drive letter representations.

### Discrepancies
- N/A

### Investigation History
1. Observed `InitService` source code. Found manual `os.path` joining on package resources.
2. Created remote probe on Windows CI. Confirmed `InitService` path resolution is correct on the runner.
3. Executed full test suite (Unit, Integration, Acceptance) on Windows CI. All tests PASSED.
4. Analyzed failing CI logs from `main` branch. Identified `vulture` and `pip-audit` as the hard blocking failures.
5. Resolved dependency conflict in `pyproject.toml` and updated `vulture_whitelist.py`.

## Solution
### Implemented Fixes
- Updated `vulture_whitelist.py` and `pyproject.toml` to suppress false-positive dead code detection in core ports/interfaces.
- Upgraded `litellm` to `^1.83.14` to resolve GHSA-xqmj-j6mv-4862.
- Narrowed project Python constraint to `">=3.11, <3.14"` and relaxed `python-dotenv` to `">=1.0.1"` to resolve dependency conflicts.
- Upgraded `pip` in the environment to resolve GHSA-58qw-9mgm-455v.

### Prevention
- Quality gate false positives are now proactively whitelisted.
- Security vulnerabilities are resolved via up-to-date dependencies and a healthy lock file.
