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
  - `true`: When `teddy update` runs, automatically run `pip install --upgrade teddy-executor` (using the same Python interpreter) and echo a clean success message.
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
      - If `auto_update: true` or `--yes` provided: Run `pip install --upgrade teddy-executor` via `sys.executable -m pip install --upgrade ...`. Echo *"Updated to vX.Y.Z."* Then pre-warm heavy imports.
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
- **Behavior:** Prints the current installed version of TeDDy (read from `importlib.metadata.version("teddy-executor")`) and exits.
- **Output format:** `TeDDy vX.Y.Z`
- **Integration:** The update checker uses the same metadata source (`importlib.metadata`) to determine the current version for comparison with the latest PyPI release. Both `--version` and the update command share the version retrieval helper.

### 3.7. Pre-warming Shared Logic

- Both `teddy init` and `teddy update` (after upgrade) execute the same import pre-warming block. Extract to a helper in `cli_helpers.py`.

---

## 4. Guidelines for Implementation

### Phase 1: Core Infrastructure
1. Extract import pre-warming into a helper function in `cli_helpers.py`.
2. Implement PyPI version check using `urllib.request` to fetch `https://pypi.org/pypi/teddy-executor/json`.
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
