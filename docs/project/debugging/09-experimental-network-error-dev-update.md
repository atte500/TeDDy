# Bug: Experimental network error and dev version shows "already latest"

- **Status:** Resolved
- **Milestone:** N/A (ad-hoc)
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

### Expected Behavior
- `teddy update --experimental` should fetch the latest dev version from TestPyPI and offer to install it.
- `teddy update` (stable) should show the latest stable version and offer to install it, even when the current version is a dev pre-release (dev > stable).

### Actual Behavior
- `teddy update --experimental` prints `"Could not check for updates: network error."`
- `teddy update` prints `"You are already running the latest version (0.1.5.dev646)."` when the user wants to install the stable release.

### Minimal Reproduction Steps
1. Install a dev version of TeDDy (e.g., 0.1.5.dev646).
2. Run `teddy update --experimental`.
3. Run `teddy update`.
4. Observe both fail to offer an upgrade.

## Context & Scope

### Regressing Delta
The `update` command in `__main__.py` calls `fetch_latest_version(index_url)` without passing `stable_only`. The function defaults to `stable_only=True`. When `--experimental` is used, `index_url` is set to `TEST_PYPI_URL`, but `stable_only=True` filters out all pre-releases, so `fetch_latest_version` returns `None`. The caller treats `None` as "network error."

For the non-experimental case, `compare_versions("0.1.5.dev646", "0.1.4")` returns `False` because `Version("0.1.5.dev646")` > `Version("0.1.4")` in PEP 440 ordering (dev pre-release of a higher version number). The `update` command treats `False` as "already running the latest version."

### Environmental Triggers
- Installed version is a dev build (e.g., 0.1.5.devXXX).
- Python environment with network access to PyPI/TestPyPI.

### Ruled Out
- (Nothing ruled out yet)

## Solution

### Root Cause
1. `fetch_latest_version` defaults to `stable_only=True`, filtering out all pre-releases. TestPyPI only hosts dev releases → returns `None` → "network error."
2. `compare_versions` uses PEP 440. Dev version `0.1.5.dev646` has epoch higher than stable `0.1.4` → returns `False` → "already latest."
3. `_is_uv_installed()` only checked `uv tool list` output; missing fallback for path-based detection.

### Fix Applied
1. **`__main__.py` `update()`:** Pass `stable_only=not experimental` to `fetch_latest_version`. After `compare_versions` returns `False`, check if current is prerelease and latest is stable → allow downgrade to stable channel.
2. **`update_checker.py` `_is_uv_installed()`:** Added path-based fallback checking common uv tool installation directories. Logged as technical debt.
3. **Existing tests:** Updated lambda mocks for `fetch_latest_version` to accept `**kwargs` so they don't break with the new `stable_only` parameter.
4. **New regression tests:** `test_experimental_and_dev_update.py` covers experimental flag, dev->stable upgrade, and notification path.

### Systemic Preventative Measures
- When adding a new parameter to a function that is commonly mocked in tests, update existing mocks to accept `**kwargs` or the new parameter to prevent test regressions.
- When a function is called with additional keyword arguments from different call sites, ensure all mocks use variadic signatures or explicit parameters.
- The `is_prerelease` check pattern can be reused wherever a "downgrade to stable" scenario arises.

## Diagnostic Analysis

### Causal Model
- `fetch_latest_version(index_url)` defaults to `stable_only=True`, which filters dev releases. TestPyPI only has dev releases → returns `None` → "network error."
- `compare_versions` uses PEP 440. Dev version `0.1.5.dev646` has epoch higher than stable `0.1.4`, so `compare_versions` returns `False` → "already latest."
- The `update` command has no special handling for when the current version is a pre-release and the latest is a stable release.

### Discrepancies
- (To be determined via probe)

### Investigation History
1. **Hypothesis: `fetch_latest_version(TEST_PYPI_URL, stable_only=True)` returns None.** Probe confirmed: Returns None (triggers "network error"). Conclusion: Experimental flag must pass `stable_only=False` to include dev releases.
2. **Hypothesis: `compare_versions("0.1.5.dev646", "0.1.4")` returns False.** Probe confirmed: Returns False (PEP 440 orders dev > stable). Conclusion: After `compare_versions`, check if current is prerelease and latest is stable — treat as upgrade needed.
3. **Hypothesis: `_is_uv_installed()` path fallback is missing.** Improved by adding path-based detection for uv-managed executable paths. Conclusion: More robust uv detection that doesn't rely solely on `uv tool list`.
4. **Hypothesis: Existing test mocks don't accept `stable_only` kwarg.** Turn 33 confirmed: 4 tests failed with `TypeError`. Conclusion: Updated lambdas to accept `**kwargs`.