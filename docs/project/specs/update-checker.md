# Spec: Update Checker & Notification

- **Status:** Active

## 1. Overview

### The Problem
Users need visibility into new TeDDy releases and a frictionless upgrade path. Currently, there is no mechanism to check for updates or notify users about newer versions.

### The Solution
Provide a lightweight update system with:
1. A dedicated `teddy update` command for manual version checking and display of upgrade instructions.
2. A `--version` flag that displays the current installed version of TeDDy.
3. A non-blocking background check that runs at the start of `teddy start` and `teddy resume`, writing the latest version to a cache file.
4. A startup notification display that reads the cache on subsequent sessions and non-intrusively notifies the user if a newer version is available.
5. A daily cache to avoid redundant PyPI requests.
6. An `--experimental` flag on `teddy update` that checks from TestPyPI for pre-release versions.

**Design Decision:** The system is notification-only. There is no auto-upgrade or `auto_update` config. The `teddy update` command always shows manual upgrade instructions (`pip install --upgrade teddy-cli`). The user must manually run the pip command to upgrade.

---

## 2. Guiding Principles / Core Logic

- **Frictionless:** Users should never be blocked or significantly delayed by version checks.
- **Non-blocking Background Checks:** In `start`/`resume`, the version check runs as an early, non-blocking daemon thread. It writes the result to a cache file.
- **Startup Notification:** On every session startup, the system reads the cache file and displays a notification if a newer version is available. The notification is displayed after the background thread has started, ensuring it appears without blocking.
- **No Auto-Update:** The system never upgrades automatically. The `teddy update` command always displays manual pip instructions.
- **Cache:** Check results are cached in `.teddy/.update_cache.json` with a 24-hour TTL to avoid hitting PyPI on every invocation.

---

## 3. Technical Specification

### 3.1. `teddy update` Command

- **Signature:** `teddy update`
- **Command Docstring:** *"Checks PyPI for the latest version of TeDDy and displays upgrade instructions."*
- **Options:**
  - `--experimental`: Check and display instructions for upgrading from TestPyPI instead of PyPI.
- **Behavior:**
  1. Check PyPI (or TestPyPI if `--experimental`) for the latest published version of `teddy-cli`.
  2. Compare against the current installed version (read from `importlib.metadata`).
  3. If no newer version: echo *"You are already running the latest version (X.Y.Z)."*
  4. If newer version available: echo *"A new version X.Y.Z is available."* followed by *"To upgrade, run: pip install --upgrade teddy-cli"* (or with `--index-url` for experimental).
  5. After the upgrade instructions, display: *"To apply prompt updates: delete .teddy/prompts/ and run 'teddy init'"*.
  6. Never attempts to install automatically. No pre-warming of imports.

### 3.2. Background Version Check (in `start`/`resume`)

- **Trigger:** Runs early in the execution of these commands, before the main logic.
- **Mechanism:**
  1. A daemon thread calls `background_check(cache_path)` which fetches the latest version from PyPI and writes it to the cache file.
  2. The main thread immediately proceeds without waiting.
  3. The cache file is written atomically (write to temp file, rename).
- **Notification Behavior:**
  - After starting the background thread, the main thread reads the cache file (which may be from a previous session) and displays a non-blocking notification if the cached version is newer than the current installed version.
  - If the cache is missing or expired, no notification is shown until the background check completes (which writes the cache for the next session).
  - Notification format: Yellow-colored text, two lines:
    `ℹ A new version X.Y.Z is available. To upgrade, run: pip install --upgrade teddy-cli`
    `   To apply prompt updates: delete .teddy/prompts/ and run 'teddy init'`

### 3.3. Cache File: `.teddy/.update_cache.json`

- **Structure:**
  ```json
  {
    "latest_version": "1.2.3",
    "checked_at": "2026-06-09T14:00:00+00:00"
  }
  ```
- **TTL:** 24 hours from `checked_at`.
- **Creation:** Created on first background check. Missing or corrupt cache file treated as expired cache.

### 3.4. `--version` Flag

- **Command:** `teddy --version` (also available as `teddy version` for consistency with other subcommands).
- **Behavior:** Prints the current installed version of TeDDy (read from `importlib.metadata.version("teddy-cli")`) and exits.
- **Output format:** `TeDDy vX.Y.Z`

### 3.5. `--experimental` Flag

- **Command:** `teddy update --experimental`
- **Behavior:** Instead of checking PyPI (`https://pypi.org/pypi/teddy-cli/json`), check TestPyPI (`https://test.pypi.org/pypi/teddy-cli/json`) for the latest version. Display upgrade instructions with `--index-url https://test.pypi.org/simple/`.
- **Output:** The notification indicates this is an experimental release (e.g., *"A new experimental version X.Y.Z is available."*).
- **No background check change:** The background check in `start`/`resume` stays on PyPI. `--experimental` is only for manual `teddy update` invocations.
- **Note on index URL:** For `pip install` from TestPyPI, use `--index-url https://test.pypi.org/simple/` (the simple index), NOT `https://test.pypi.org/legacy/` (which is the upload API endpoint used in CI).
- **Version comparison:** The same version comparison logic is used as for PyPI checks. Versions from TestPyPI are expected to follow PEP 440 (e.g., `0.1.0.dev<run_number>`).

---

## 4. Prototype Validation

The prototype documented in `spikes/prototypes/update-checker/` was built and executed against the real system, exercising all key risk areas with real dependencies (no mocking of core logic). Below are the validated results.

### Validated Risk Areas

| Risk Area | Result | Detail |
|-----------|--------|--------|
| **Version detection** | ✓ Verified | `get_current_version()` returned `'0.1.3'` via `importlib.metadata.version("teddy-cli")` |
| **Real PyPI fetch** | ✓ Verified | `fetch_latest_version()` returned `'0.1.4'` via real `urllib.request` HTTP call |
| **Version comparison** | ✓ Verified | Edge cases confirmed: invalid versions → `False`, empty strings → `False`, same version → `False` |
| **Cache I/O lifecycle** | ✓ Verified | Write succeeds, read valid → dict, corrupt JSON → `None`, missing file → `None`, expired TTL → `None`, fresh TTL → valid data |
| **Background daemon thread** | ✓ Verified | Non-blocking (main thread delay: ~0.0007s), daemon thread completed and wrote cache automatically |
| **Startup notification display** | ✓ Verified | Reads cache, compares versions, displays notification non-blockingly |

### Key Findings
- **Version drift:** The current installed version is `0.1.3` (not `0.1.0` as referenced in earlier slice scenarios). PyPI reports `0.1.4` available as of 2026-06-22.
- **Non-blocking verified:** Background daemon threads with `daemon=True` allow the main thread to continue processing immediately (~0.0007s overhead for thread creation vs ~0.5s for a real HTTP fetch).
- **compare_versions edge cases:** Returns `False` for any parse failure — invalid strings (`"abc"`), empty strings (`""`), and equal versions all correctly return `False`. Only strictly greater PEP 440 versions return `True`.
- **Atomic cache writes work:** The write-to-temp-then-rename pattern prevents partial reads by other threads or processes.
- **Cache path:** The cache file path should be `.teddy/.update_cache.json` (consistent with the `.teddy` directory convention).
