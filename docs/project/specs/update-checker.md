# Spec: Update Checker & Auto-Update

- **Status:** Active

## 1. Overview

### The Problem
Users need visibility into new TeDDy releases and a frictionless upgrade path. Currently, there is no mechanism to check for updates or notify users about newer versions.

### The Solution
Provide a comprehensive update system with:
1. A dedicated `teddy update` command for manual version checking and upgrading.
2. A `--version` flag that displays the current installed version of TeDDy.
3. A lightweight, non-blocking background check that runs at the start of `teddy start`, `teddy resume`, and `teddy execute`.
4. An `auto_update` configuration setting (default: `true`) that automatically installs upgrades when a newer version is detected.
5. A daily cache to avoid redundant PyPI requests.
6. An `--experimental` flag on `teddy update` that checks and upgrades from TestPyPI for pre-release versions.

---

## 2. Guiding Principles / Core Logic

- **Frictionless:** Users should never be blocked or significantly delayed by version checks.
- **Transparency:** The system always notifies the user about version changes and upgrade actions, but the notification must be clean and non-intrusive.
- **Opt-Out Control:** Users can disable auto-update via the `auto_update` config key.
- **Non-blocking Background Checks:** In `start`/`resume`/`execute`, the version check runs as an early, non-blocking background task. If a newer version is found, a cached state is set; the actual upgrade is deferred to `teddy update`.
- **Cache:** Check results are cached in `.teddy/.update_cache.json` with a 24-hour TTL to avoid hitting PyPI on every invocation.

---

## 3. Technical Specification

### 3.1. Config Key: `auto_update`

- **Location:** `.teddy/config.yaml`
- **Key:** `auto_update`
- **Type:** boolean
- **Default:** `true`
- **Behavior:**
  - `true`: When `teddy update` runs, automatically run `pip install --upgrade teddy-cli` (using the same Python interpreter) and echo a clean success message.
  - `false`: When a newer version is found, echo a clean notification: *"A new version X.Y.Z is available. Run 'teddy update' to upgrade."* Do NOT auto-install.

### 3.2. `teddy update` Command

- **Signature:** `teddy update`
- **Command Docstring:** *"Checks PyPI for the latest version of TeDDy and upgrades if a newer release is available. Pre-warms heavy imports after upgrade."*
- **Options:**
  - `--yes, -y`: Force upgrade even if `auto_update: false`.
- **Behavior:**
  1. Check PyPI for the latest published version of `teddy-executor`.
  2. Compare against the current installed version (read from `importlib.metadata`).
  3. If no newer version: echo *"You are already running the latest version (X.Y.Z)."*
  4. If newer version available:
      - If `auto_update: true` or `--yes` provided: Run `pip install --upgrade teddy-cli` via `sys.executable -m pip install --upgrade ...`. Echo *"Updated to vX.Y.Z."* Then pre-warm heavy imports.
      - If `auto_update: false` and no `--yes`: Echo *"A new version X.Y.Z is available. Run 'teddy update --yes' to upgrade."*
  5. Pre-warm heavy imports **only after a successful upgrade**.
  6. **Prompt update notification:** After the version check (regardless of upgrade outcome), if `.teddy/prompts/` exists, print a styled notification directing the user to apply prompt updates. The notification MUST use colored output (e.g., `rich` or `typer.style()`) to draw attention. Example rendering:

     ```
     ═══════════════════════════════════════════════
     💡 Prompt Update Notice:
     To apply prompt updates from this release:
     1. Delete `.teddy/prompts/`
     2. Run `teddy init`
     ═══════════════════════════════════════════════
     ```

     The exact styling (color, borders, icons) should be consistent with the existing CLI formatting patterns in the codebase (see `cli_formatter.py` for guidelines). This notification is intentionally unconditional — it appears on every `teddy update` invocation to ensure users are always aware of the manual update path for custom prompts.

### 3.3. Background Version Check (in `start`/`resume`/`execute`)

- **Trigger:** Runs early in the execution of these commands, before the main logic.
- **Mechanism:**
  1. Check `.teddy/.update_cache.json` for a cached result with a timestamp less than 24 hours old.
  2. If cache is valid, use cached comparison result.
  3. If cache is expired or missing, perform a PyPI check in a background daemon thread (non-blocking).
  4. When cache is updated, write the result to `.teddy/.update_cache.json` with structure: `{"latest_version": "X.Y.Z", "checked_at": "ISO-8601 timestamp"}`.
- **Notification Behavior:**
  - The background check is purely informational and non-blocking.
  - If a newer version is found, the next invocation of `teddy update` will handle the upgrade (blocking).
  - If `auto_update: false`, after the main command output, append: *"ℹ A new version X.Y.Z is available. Run 'teddy update' to upgrade."*

### 3.4. Cache File: `.teddy/.update_cache.json`

- **Structure:**
  ```json
  {
    "latest_version": "1.2.3",
    "checked_at": "2026-06-09T14:00:00+00:00"
  }
  ```
- **TTL:** 24 hours from `checked_at`.
- **Creation:** Created on first check. Missing or corrupt cache file treated as expired cache.

### 3.5. Pre-warming After Upgrade

- After a successful `teddy update`, pre-warm heavy imports:
  ```python
  try:
      import litellm  # noqa: F401
      import trafilatura  # noqa: F401
      import pyperclip  # noqa: F401
      from bs4 import BeautifulSoup  # noqa: F401
      from ddgs import DDGS  # noqa: F401
  except ImportError:
      pass
  ```
- This logic should be extracted into a shared helper function (e.g., `_prewarm_imports()`) in `cli_helpers.py` to avoid duplication with `teddy init`.

### 3.6. `--version` Flag

- **Command:** `teddy --version` (also available as `teddy version` for consistency with other subcommands).
- **Behavior:** Prints the current installed version of TeDDy (read from `importlib.metadata.version("teddy-cli")`) and exits.
- **Output format:** `TeDDy vX.Y.Z`
- **Integration:** The update checker uses the same metadata source (`importlib.metadata`) to determine the current version for comparison with the latest PyPI release. Both `--version` and the update command share the version retrieval helper.

### 3.7. Pre-warming Shared Logic

- Both `teddy init` and `teddy update` (after upgrade) execute the same import pre-warming block. Extract to a helper in `cli_helpers.py`.

### 3.8. `--experimental` Flag

- **Command:** `teddy update --experimental`
- **Behavior:** Instead of checking PyPI (`https://pypi.org/pypi/teddy-cli/json`), check TestPyPI (`https://test.pypi.org/pypi/teddy-cli/json`) for the latest version. If a newer version is found, install from TestPyPI using `--index-url https://test.pypi.org/simple/`.
- **Output:** The version notification and upgrade message MUST indicate this is an experimental release (e.g., *"Updated to experimental vX.Y.Z.dev..."*).
- **No background check change:** The background check in `start`/`resume`/`execute` stays on PyPI. `--experimental` is only for manual `teddy update` invocations.
- **Config interaction:** Respects `auto_update` setting. If `auto_update: true`, automatically upgrade from TestPyPI. If `auto_update: false`, notify the user to run `teddy update --experimental --yes` to upgrade.
- **Note on index URL:** For `pip install` from TestPyPI, use `--index-url https://test.pypi.org/simple/` (the simple index), NOT `https://test.pypi.org/legacy/` (which is the upload API endpoint used in CI).
- **Version comparison:** The same version comparison logic is used as for PyPI checks. Versions from TestPyPI are expected to follow PEP 440 (e.g., `0.1.0.dev<run_number>`).

---

## 5. Prototype Validation

The prototype documented in `spikes/prototypes/update-checker/` was built and executed against the real system, exercising all key risk areas with real dependencies (no mocking of core logic). Below are the validated results.

### Validated Risk Areas

| Risk Area | Result | Detail |
|-----------|--------|--------|
| **Version detection** | ✓ Verified | `get_current_version()` returned `'0.1.3'` via `importlib.metadata.version("teddy-cli")` |
| **Real PyPI fetch** | ✓ Verified | `fetch_latest_version()` returned `'0.1.4'` via real `urllib.request` HTTP call |
| **Version comparison** | ✓ Verified | Edge cases confirmed: invalid versions → `False`, empty strings → `False`, same version → `False` |
| **Cache I/O lifecycle** | ✓ Verified | Write succeeds, read valid → dict, corrupt JSON → `None`, missing file → `None`, expired TTL → `None`, fresh TTL → valid data |
| **Background daemon thread** | ✓ Verified | Non-blocking (main thread delay: ~0.0007s), daemon thread completed and wrote cache automatically |
| **Prewarm imports extraction** | ✓ Verified | Both `shadow_cli_helpers` and `shadow_update_checker` implementations execute without error |
| **should_update logic** | ✓ Verified | No cache → `None`, older version → `None`, newer + `auto_update=True` → `True`, newer + `auto_update=False` → `False` |
| **Upgrade command construction** | ✓ Verified | Command verified: `sys.executable -m pip install --upgrade teddy-cli [--index-url ...]` (not executed) |

### Key Findings
- **Version drift:** The current installed version is `0.1.3` (not `0.1.0` as referenced in earlier slice scenarios). PyPI reports `0.1.4` available as of 2026-06-22.
- **Non-blocking verified:** Background daemon threads with `daemon=True` allow the main thread to continue processing immediately (~0.0007s overhead for thread creation vs ~0.5s for a real HTTP fetch).
- **compare_versions edge cases:** Returns `False` for any parse failure — invalid strings (`"abc"`), empty strings (`""`), and equal versions all correctly return `False`. Only strictly greater PEP 440 versions return `True`.
- **Atomic cache writes work:** The write-to-temp-then-rename pattern prevents partial reads by other threads or processes.
- **prewarm_imports is safe:** Import errors are silently caught; the function works identically when extracted to `cli_helpers.py`.
- **Cache path:** The cache file path should be `.teddy/.update_cache.json` (consistent with the `.teddy` directory convention).

---

## 4. Guidelines for Implementation

### Phase 1: Core Infrastructure
1. Extract import pre-warming into a helper function in `cli_helpers.py`.
2. Implement PyPI version check using `urllib.request` to fetch `https://pypi.org/pypi/teddy-cli/json`.
   - Note: The same function should accept an optional `index` parameter to switch between PyPI and TestPyPI URLs for the `--experimental` flag.
3. Compare versions using `packaging.version` or simple `tuple(map(int, ...))`.
4. Implement daily cache read/write in `_update_cache.json`.

### Phase 2: Commands
1. Add `teddy update` command to `__main__.py`.
2. Add background check in `start`/`resume`/`execute` handlers (in `session_cli_handlers.py`).

### Phase 3: Config Integration
1. Add `auto_update: true` to `config.yaml` template.
2. Wire config reading for `auto_update` in the update logic.
3. Ensure `auto_update: false` suppresses auto-install.

### Phase 4: Testing & Documentation
1. Unit tests for version comparison, cache, and pre-warming.
2. Update CLI architecture doc and README.

### Phase 5: Experimental Flag
1. Add `--experimental` option to the `teddy update` command.
2. Implement TestPyPI URL resolution (use `https://test.pypi.org/pypi/teddy-cli/json` for version check and `--index-url https://test.pypi.org/simple/` for pip install).
3. Update the upgrade path to conditionally use TestPyPI when `--experimental` is provided.
4. Ensure version notifications distinctly label experimental releases.
5. Unit tests for TestPyPI fallback and experimental flag behavior.
