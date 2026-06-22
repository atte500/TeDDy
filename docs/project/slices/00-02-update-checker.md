# Slice: Update Checker & Auto-Update

- **Status:** In Progress
- **Type:** Feature
- **Milestone:** N/A (ad-hoc)
- **Specs:** [docs/project/specs/update-checker.md](/docs/project/specs/update-checker.md)
- **Prototype:** [spikes/prototypes/update-checker/](/spikes/prototypes/update-checker/)
- **Component Docs:** [docs/architecture/core/services/update_checker.md](/docs/architecture/core/services/update_checker.md)
- **Scope Slug:** `update-checker`

## Business Goal

Provide users with visibility into new TeDDy releases and a frictionless upgrade path, including a `teddy update` command, `--version` flag, and non-blocking background checks in session commands.

## Scenarios

> As a user, I want to check for updates manually so that I can decide when to upgrade.

```gherkin
Feature: Manual Update Check
  Scenario: No newer version available
    Given the current installed version is "0.1.3"
    And the latest PyPI version is "0.1.3"
    When I run "teddy update"
    Then I see "You are already running the latest version (0.1.3)."

  Scenario: Newer version available with auto_update=true
    Given the current installed version is "0.1.3"
    And the latest PyPI version is "0.2.0"
    And auto_update is set to "true" in config
    When I run "teddy update"
    Then the upgrade is executed via pip
    And I see "Updated to v0.2.0."
    And heavy imports are pre-warmed

  Scenario: Newer version available with auto_update=false
    Given the current installed version is "0.1.3"
    And the latest PyPI version is "0.2.0"
    And auto_update is set to "false" in config
    When I run "teddy update"
    Then I see "A new version 0.2.0 is available. Run 'teddy update --yes' to upgrade."

  Scenario: Force upgrade with --yes flag
    Given the current installed version is "0.1.3"
    And the latest PyPI version is "0.2.0"
    And auto_update is set to "false" in config
    When I run "teddy update --yes"
    Then the upgrade is executed via pip
    And I see "Updated to v0.2.0."

  Scenario: Experimental flag uses TestPyPI
    Given the current installed version is "0.1.3"
    And the latest TestPyPI version is "0.2.0.dev1"
    When I run "teddy update --experimental"
    Then the version check uses TestPyPI
    And the upgrade uses TestPyPI index
    And I see "Updated to experimental v0.2.0.dev1."
```

> As a user, I want to see the current version so that I know what I'm running.

```gherkin
Feature: Version Display
  Scenario: Display version via --version flag
    When I run "teddy --version"
    Then I see "TeDDy v0.1.3"

  Scenario: Display version via version subcommand
    When I run "teddy version"
    Then I see "TeDDy v0.1.3"
```

> As a user, I want a non-blocking background check so that sessions are not delayed.

```gherkin
Feature: Background Version Check
  Scenario: Cache hit within 24h
    Given the update cache exists with "0.2.0" and checked_at within 24h
    When I run "teddy start"
    Then no HTTP request is made to PyPI
    And the session starts normally

  Scenario: Cache expired or missing triggers background fetch
    Given the update cache does not exist
    When I run "teddy start"
    Then a background thread fetches the latest version
    And the session starts without blocking
    And the cache is updated with the fetched version

  Scenario: New version found in background with auto_update=false
    Given the latest version is "0.2.0"
    And auto_update is set to "false"
    When I run "teddy execute"
    Then after execution, I see "ℹ A new version 0.2.0 is available. Run 'teddy update' to upgrade."
```

> As a user, I want the prompt update notice to appear so that I know how to apply prompt changes from a release.

```gherkin
Feature: Prompt Update Notice
  Scenario: Prompt update notice appears after update
    When I run "teddy update"
    Then a styled prompt update notice is displayed
    And the notice instructs to delete prompts directory and run init
```

## Edge Cases

- **Network Failure:** If PyPI is unreachable, `fetch_latest_version` returns None and no error is shown. The cache remains unchanged.
- **Corrupt Cache:** If `.update_cache.json` has invalid JSON or missing keys, it is treated as expired and overwritten on next successful fetch.
- **Permissions Denied for pip:** If `sys.executable -m pip install` fails (e.g., not running in a virtualenv), display a clear error: "Could not upgrade: [error message]. Please run 'pip install --upgrade teddy-cli' manually."
- **Package Not Found:** If `importlib.metadata.version("teddy-cli")` raises `PackageNotFoundError`, fall back to `"0.0.0"` (dev installation).
- **Experimental + auto_update false:** When `--experimental` is used and `auto_update: false`, the notification should say: "Run 'teddy update --experimental --yes' to upgrade."
- **Race Condition:** Background thread writing cache while main thread reads it. Use atomic write (write to temp, rename) to ensure the main thread never reads a partially written file.
- **Invalid Version Strings:** If either `current` or `latest` is a non-PEP 440 string (e.g., `"abc"`, `""`), `compare_versions` returns `False`. The caller should handle this by treating a `False` return as "no update needed."
- **Empty String Comparison:** `compare_versions("", "")` returns `False` — the upgrade path is never triggered for empty/missing versions.
- **Same Version Comparison:** `compare_versions("1.0.0", "1.0.0")` returns `False` — no spurious upgrade attempts.

## Implementation Plan

### Strategy
Use a lightweight utility module in `core/services/update_checker.py` (Option B). No new ports or adapters needed. Extract the pre-warming logic from `__main__.py` into `cli_helpers.py` to avoid duplication. The update command, `--version` flag, and background checks are wired directly into the existing CLI handler functions.

### Key Guidelines
- All HTTP calls use `urllib.request` (stdlib) — no new dependencies.
- Version comparison uses `packaging.version.Version` (already transitive via `pip-audit`).
- Cache file lives at `.teddy/.update_cache.json`.
- Background check runs as a daemon thread in `handle_new_session` and `handle_resume_session`.
- The daemon thread is truly non-blocking (~0.0007s overhead for main thread) — verified in prototype.
- Daemon threads auto-terminate when the main process exits; no explicit shutdown needed.
- The `update` command is a standalone Typer command in `__main__.py`.
- Pre-warming is extracted to `cli_helpers.prewarm_imports()` and called by both `init` and `update`.
- The `should_update` function takes an `auto_update_enabled: bool` parameter directly (not a config service).

### Prototype Findings
The [prototype](/spikes/prototypes/update-checker/) validated all 8 risk areas:

| Risk Area | Status | Detail |
|-----------|--------|--------|
| Version detection | ✓ | `get_current_version()` returns `'0.1.3'` (real installed version) |
| Real PyPI fetch | ✓ | Returns `'0.1.4'` from PyPI JSON API (live HTTP) |
| Version comparison | ✓ | All edge cases verified — invalid/empty/equal→False |
| Cache I/O lifecycle | ✓ | Write/read/corrupt/missing/expired/fresh all verified |
| Background daemon thread | ✓ | Non-blocking (0.0007s main thread delay), auto-writes cache |
| Prewarm imports extraction | ✓ | Both implementations execute without error |
| should_update logic | ✓ | None/True/False all correct |
| Upgrade command construction | ✓ | Command verified (not executed) |

## Deliverables

### Contract (Seam Definition)
- [x] **Contract** - Define `prewarm_imports()` function signature in `cli_helpers.py` (extracted from `__main__.py`).

### Harness (Test Infrastructure)
- [ ] **Harness** - Verify `packaging` is available as transitive dependency (via `pip-audit`).
- [ ] **Harness** - Create a `FakeHTTPResponse` test helper to simulate PyPI JSON responses in unit tests.
- [ ] **Harness** - Create test fixture for isolated temp cache directory.

### Logic (Business Logic Implementation)
- [ ] **Logic** - Implement `src/teddy_executor/core/services/update_checker.py` with: `get_current_version`, `fetch_latest_version`, `compare_versions`, `read_update_cache`, `write_update_cache`, `perform_upgrade`, `background_check`, `should_update`.
- [ ] **Logic** - Extract and implement `prewarm_imports()` in `cli_helpers.py` (shared seam: consumed by init + update).
- [ ] **Logic** - Update `__main__.py` `init` command to use `prewarm_imports()` from `cli_helpers`.

### Wiring (CLI Integration)
- [x] **Wiring** - `--version` flag in Typer `main_callback` (already implemented).
- [x] **Wiring** - `version` subcommand in `__main__.py` (already implemented).
- [ ] **Wiring** - Add `update` command with `--yes` and `--experimental` options in `__main__.py`.
- [ ] **Wiring** - Add background version check call in `session_cli_handlers.py` (`handle_new_session` and `handle_resume_session`).
- [ ] **Wiring** - Add `auto_update: true` key to `config.yaml` baseline.
- [ ] **Wiring** - Read `auto_update` config in update command (via `IConfigService.get_setting("auto_update")`).

### Testing (Unit & Acceptance)
- [ ] **Test** - Unit tests for `update_checker.py` (version comparison, cache I/O, fetch resilience, upgrade command, should_update logic).
- [ ] **Test** - Unit tests for `prewarm_imports()` extraction (verify it executes without error).
- [ ] **Test** - Acceptance test for `teddy update` happy path (newer version → upgrade).
- [ ] **Test** - Acceptance test for `teddy --version` (displays correct version).
- [ ] **Test** - Acceptance test for `teddy update --experimental` (TestPyPI URL resolution).

### Documentation
- [ ] **Documentation** - Update `README.md` with `version` and `update` command usage after implementation.

## Implementation Notes

### Contract — `prewarm_imports()` extraction
- **Function:** `prewarm_imports()` added to `src/teddy_executor/adapters/inbound/cli_helpers.py` at line 252.
- **Body:** Identical to the inline block in `__main__.py`'s `init` command (5 heavy-import packages: litellm, trafilatura, pyperclip, BeautifulSoup, DDGS).
- **Test:** `test_prewarm_imports_executes_without_error` added to `tests/suites/unit/adapters/inbound/test_cli_helpers.py`.
- **Test outcome:** Red → `ImportError: cannot import name 'prewarm_imports'`. Green → 2 tests pass.
- **Full suite:** 956 passed, 3 skipped — no regressions.
- **Rationale:** Extracted to `cli_helpers.py` to create a shared seam between the `init` command and the upcoming `update` command (which also needs to pre-warm imports post-upgrade). Avoids code duplication while keeping the function in the adapter layer (not core).
- **Architecture doc sync:** The `update_checker.md` architecture doc already references `prewarm_imports` as living in `cli_helpers.py`. No update needed.

## Verification

1. ✓ Run `poetry run teddy --version` — prints "TeDDy v0.1.3"
2. ✓ Run `poetry run teddy version` — prints same
3. Run `poetry run teddy update` while offline — should print "Could not check for updates: [error]" or fallback silently (prototype confirmed: network failure returns None without error)
4. Run `poetry run teddy update` with network — should check PyPI and either update or report up-to-date
5. Run `teddy start` — session starts without blocking delay (prototype confirmed: background thread is non-blocking, ~0.0007s overhead)
6. Set `auto_update: false` in `.teddy/config.yaml`, run `teddy update` — should show notification only
7. Run `poetry run teddy update` when cache is valid (within 24h) — no HTTP request made
8. Run full test suite to ensure no regressions
