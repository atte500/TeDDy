# Bug: Update version not persisting after teddy update

- **Status:** Resolved
- **Milestone:** N/A (ad-hoc)
- **Vertical Slice:** N/A
- **Specs:** [docs/project/specs/update-checker.md](/docs/project/specs/update-checker.md)

## Symptoms

### Expected Behaviour
After running `teddy update --experimental`, the version displayed by `teddy version` should reflect the newly installed version (e.g., `v0.1.5.dev644`). Similarly for `teddy update` (stable channel).

### Actual Behaviour
- `teddy update --experimental` outputs `Updated to v0.1.5.dev644.`
- Immediately afterwards, `teddy version` still shows `Teddy v0.1.5.dev643` (the old version).
- Even running `teddy update` (non‑experimental) says `Updated to v0.1.4.`, but version remains `v0.1.5.dev643`.

The update claims success but the actual installed package never changes (or changes in a location not read by the running tool).

### Minimal Reproduction Steps
1. Check current version: `teddy version`
2. Run update: `teddy update --experimental` (or `teddy update`)
3. Check version again: `teddy version`
4. Observe that version is unchanged despite success message.

## Context & Scope

### Regressing Delta
Two fix commits that are NOT ancestors of HEAD:
- `cf569b87` ("fix(update): replace should_update(None) guard with direct config check") – Replaced `should_update(None, ...)` (which always returns `None`) with a direct check of the `auto_update` config and `--yes` flag.
- `79940b14` ("fix(update): wire perform_upgrade in update command success branch") – Replaced the hardcoded "Updated to..." echo with an actual call to `perform_upgrade(latest, index_url=index_url)`.

Current HEAD at `main` is missing both changes, meaning the update command:
1. Calls `should_update(None, ...)` → always returns `None` → goes to `else` branch "already latest" (or in some code paths, the hardcoded success path may be hit but the action is never taken because `should_update` returned `None`).
2. Even if the `action is True` branch were reached, it would print success without ever calling `perform_upgrade`.

### Environmental Triggers
- TeDDy installed via `uv tool install teddy-cli`.
- The `perform_upgrade` function uses `sys.executable -m pip install --upgrade teddy-cli` which may fail silently or install to a non-uv-managed location.

### Ruled Out
- (Nothing ruled out yet – investigation still starting.)

## Solution

### Root Cause
Two missing commits that were never merged into `main`:

1. **Missing commit `cf569b87`** — The `update` command in `__main__.py` called `should_update(None, ...)`, which returns `None` due to the defensive `if cache_path is None: return None` guard. The caller treated `None` as "no update needed", silently blocking the upgrade path.

2. **Missing commit `79940b14`** — Even if the `should_update` issue were bypassed, the success branch printed "Updated to v{latest}" without ever calling `perform_upgrade()`. The actual `pip install` or `uv tool upgrade` command was never executed, so the installed package version never changed.

Both fixes existed in separate commits but were never merged into the `main` branch.

### Fix Applied
1. **Removed `should_update` from imports** in the `update()` function and deleted the `action = should_update(None, auto_update_enabled=auto_update)` call.
2. **Replaced with direct config check:** `if auto_update or yes:` — reads the `auto_update` setting from `IConfigService` directly.
3. **Wired `perform_upgrade`:** In the success branch, now calls `perform_upgrade(latest, index_url=index_url)` with proper success/failure handling. On failure, prints an error message and exits with code 1.

### Systemic Preventative Measures
- **Category A (Unwired Functions):** When implementing a utility function that is meant to be called from a CLI command, write a regression test FIRST that mocks the utility function and asserts it is called with the correct arguments. This prevents future wiring gaps.
- **Category B (None Propagation):** When a function returns `None` as a defensive guard for `Optional` inputs, ensure callers never pass `None` without an explicit fallback. Avoid using `None` as a tristate sentinel (`True`/`False`/`None`) where the caller might confuse "no update needed" with "defensive early return." Use separate sentinel values or raise a typed exception.
- **Regression Test:** `test_update_command_actually_upgrades.py` covers three scenarios: success path (calls `perform_upgrade`, prints success, prewarms imports), failure path (calls `perform_upgrade`, prints error, exits with 1), and notification path (`auto_update=false`, shows --yes instruction). A fourth safety-net test scans `__main__.py` for the hardcoded comment and verifies `perform_upgrade` is present in the source.

## Technical Debt Logged
- None new. The existing debt entry in PROJECT.md about `perform_upgrade` using `sys.executable -m pip install` incompatible with `uv tool install` is partially mitigated — the current `perform_upgrade` function already detects uv and uses `uv tool upgrade teddy-cli`. However, if uv is not on PATH but the package was installed via uv tool, the fallback to `sys.executable -m pip` may silently install to the wrong environment. This is a known limitation documented in PROJECT.md.

## Diagnostic Analysis

### Causal Model

**Bug 1: `should_update(None)` blocks upgrade path**
- The `update` command calls `should_update(cache_path=None, auto_update_enabled=auto_update)`.
- Inside `should_update`, the guard `if cache_path is None: return None` immediately returns `None`.
- The caller interprets `None` as "no update needed" and either prints "already latest" or (in a different branch) does nothing.
- Result: even when PyPI reports a newer version, `should_update` blocks the upgrade path.

**Bug 2: Hardcoded success without actual upgrade**
- In the `action is True` branch (which is unreachable due to Bug 1 in current HEAD, but was reachable in earlier code), the command prints "Updated to v{latest}" but never calls `perform_upgrade()`.
- The version displayed by `teddy version` reads from `importlib.metadata`, which reflects the actual installed package. Since no upgrade was performed, the version never changes.

**Combined effect:**
- User sees "Updated to vX.Y.Z." (from the hardcoded branch in their installed version) or "You are already running the latest version" (from the `should_update` branch in current HEAD).
- `teddy version` always returns the old installed version because `perform_upgrade()` was never called.

**Note:** The `perform_upgrade` function in `update_checker.py` is correctly implemented (handles uv and pip). The only issue is that `__main__.py`'s `update` command never calls it.

### Discrepancies
- (Resolved: The fix commits are not ancestors of HEAD, confirming the regressing delta. Investigation history now documents the missing commits.)
- `should_update(None, ...)` returns `None` due to the `None` guard, blocking the upgrade path. The fix (commit cf569b87) replaces the `should_update` call with a direct config check. This is now proven via git history.
- The `action is True` branch prints success without calling `perform_upgrade`. The fix (commit 79940b14) wires `perform_upgrade`. This is now proven via git history.
- No evidence that `perform_upgrade` prints success on failure — that was a false hypothesis. The function correctly returns `False` on failure.

### Investigation History
1. **Hypothesis: The update command never calls perform_upgrade.** Observed via `git log` that commits `79940b14` (wire perform_upgrade) and `cf569b87` (replace should_update guard) are NOT ancestors of HEAD. Conclusion: The current HEAD is missing both fixes, confirming the root cause. The update command has hardcoded success and `should_update(None)` blocks the upgrade path.
