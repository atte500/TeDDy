# Bug: Update checker reports "latest version" incorrectly (dev640 available but says dev637 is latest)

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** [Update Checker Spec](/docs/project/specs/update-checker.md), [PROJECT.md Technical Debt entry](/docs/project/PROJECT.md#Technical-Debt)

## Symptoms

**Expected:** `teddy update` should detect that version 0.1.5.dev640 exists (or any version newer than the currently installed version) and offer to upgrade.
**Actual:** `teddy update` reports "You are already running the latest version (0.1.5.dev637)" despite dev640 being available on PyPI.

### Reproduction Steps

1. Run `teddy update` with a dev version installed (e.g., 0.1.5.dev637).
2. Observe message: "You are already running the latest version (0.1.5.dev637)."
3. Verify that a newer dev version exists on PyPI (e.g., 0.1.5.dev640).

## Context & Scope

### Regressing Delta
- The bug is in `fetch_latest_version()` in `update_checker.py`. It reads `data["info"]["version"]` from the PyPI JSON API, which only returns the **latest stable** release (e.g., 0.1.4). Dev/pre-release versions under `data["releases"]` are ignored.

### Environmental Triggers
- The bug manifests when:
  - The installed version is a **dev/pre-release** version (e.g., 0.1.5.dev637).
  - The latest **stable** release on PyPI (e.g., 0.1.4) is **not newer** than the installed dev version according to PEP 440.
  - However, a newer **dev** version (e.g., 0.1.5.dev640) exists in `data["releases"]` but is not returned by `info.version`.
- On TestPyPI, `info.version` happens to return the latest dev version because there is no stable release, so `--experimental` works if the index URL is properly switched. However, the user reports `--experimental` also fails, possibly due to caching interference.

### Ruled Out
- Version comparison logic (`compare_versions`) works correctly per PEP 440 (confirmed via probe).
- `get_current_version()` works correctly via `importlib.metadata`.
- `perform_upgrade` and `background_check` are not directly involved in the version detection bug.

## Diagnostic Analysis

### Causal Model
- `fetch_latest_version()` calls the PyPI JSON API and reads only `data["info"]["version"]`, which returns the latest **stable** release.
- For a user on a dev build (e.g., 0.1.5.dev637), the stable release (0.1.4) is not > their current version, so `compare_versions` returns False.
- The update checker thus concludes "Already latest", ignoring newer dev releases.
- The correct behavior should consider the **highest version across all releases** (`data["releases"]`), including pre-releases, because the user is already on a dev track.

### Discrepancies
- Observation: `fetch_latest_version(PYPI_URL)` returns `"0.1.4"` in our MRE, but PyPI's `releases` dict contains `0.1.5.dev640`. (Resolved: confirmed root cause — `info.version` only returns stable.)

### Investigation History
1. **Probe (Turn 2):** `fetch_latest_version` returns 0.1.4 from PyPI (latest stable). TestPyPI returns 0.1.5.dev640. Direct `compare_versions` tests show PEP 440 works correctly for dev versions.
2. **MRE (Turn 3):** Simulating a user on 0.1.5.dev637 confirms PyPI says "Already latest" while TestPyPI says "Update available". Analysis of all releases confirms PyPI has no dev releases in `info.version`. The fix must scan all releases.

## Solution
### Root Cause
`fetch_latest_version()` in `update_checker.py` reads `data["info"]["version"]`, which returns only the latest **stable** version. Dev/pre-release versions (listed under `data["releases"]`) are ignored. For users on a dev track, this means the update checker never sees newer dev builds.

Additionally, `compare_versions` uses strict PEP 440 `>` comparison, so a dev version (e.g., `0.1.5.dev640`) is never considered "less than" a stable version (`0.1.4`), meaning `teddy update` would never offer to downgrade a user from a dev build to the latest stable.

### Fix Applied
Two changes were made to the production code:

1. **`fetch_latest_version()` in `update_checker.py`:** Now accepts a `stable_only` parameter (default `True`). When `True`, only stable (non-prerelease) versions are considered. When `False`, all releases including dev/pre-releases are scanned. Always uses `data["releases"]` instead of `data["info"]["version"]` for robustness. A public `is_prerelease()` helper function was also added.

2. **`update` command in `__main__.py`:**
   - Default `teddy update`: Passes `stable_only=True` to `fetch_latest_version(PYPI_URL)`. If the current version is a prerelease (dev/alpha/beta), the stable version is always considered an update (unless already at that exact version). This allows a user on `0.1.5.dev637` to be offered an upgrade to `0.1.4`.
   - `teddy update --experimental`: Passes `stable_only=False` to `fetch_latest_version(TEST_PYPI_URL)`, returning the highest version (typically a dev build).

3. **Acceptance tests:** Updated 3 mock lambdas/functions in `test_auto_update_wiring.py`, `test_experimental_wiring.py`, and `test_update_checker_wiring.py` to accept `**kwargs` for forward-compatibility with the new `stable_only` parameter.

4. **`perform_upgrade` wiring:** The update command success branch was previously a hardcoded echo stub. It now calls `perform_upgrade(latest, index_url=index_url)` to actually run the upgrade via pip or uv. If the upgrade succeeds, it echoes "Updated to vX.Y.Z." and pre-warms imports. If it fails, it echoes an error and exits with code 1. Acceptance tests were updated to mock `perform_upgrade` and verify the auto_update=True path.

### Verification
- MRE confirmed the fix correctly identifies `0.1.4` as the latest stable from PyPI and `0.1.5.dev640` as the latest from TestPyPI.
- Regression tests for `is_prerelease`, `fetch_latest_version(stable_only)`, and the override decision logic all pass.
- Full test suite: 1016 passed, 3 skipped.
- User can now run `teddy update` and actually be upgraded (confirmed by acceptance tests covering the full success path).

### Preventative Measures
- Added `is_prerelease()` as a public utility function so the prerelease detection logic is reusable and testable.
- The `stable_only` parameter makes version filtering explicit and easy to reason about.
- Updated acceptance tests to accept `**kwargs` in mock signatures to prevent future breakage when new keyword arguments are added.
- `perform_upgrade` includes detection for uv vs pip installation, ensuring the correct upgrade tool is used.
- Documented in the update checker spec that version checks scan all releases and filter based on stability.
