# Slice: Update Checker & Auto-Update

- **Status:** To De-risk
- **Type:** Feature
- **Milestone:** N/A (ad-hoc)
- **Specs:** [docs/project/specs/update-checker.md](/docs/project/specs/update-checker.md)
- **Component Docs:** [docs/architecture/core/services/update_checker.md](/docs/architecture/core/services/update_checker.md)
- **Scope Slug:** `update-checker`

## Business Goal

Provide users with visibility into new TeDDy releases and a frictionless upgrade path, including a `teddy update` command, `--version` flag, and non-blocking background checks in session commands.

## Scenarios

> As a user, I want to check for updates manually so that I can decide when to upgrade.

```gherkin
Feature: Manual Update Check
  Scenario: No newer version available
    Given the current installed version is "0.1.0"
    And the latest PyPI version is "0.1.0"
    When I run "teddy update"
    Then I see "You are already running the latest version (0.1.0)."

  Scenario: Newer version available with auto_update=true
    Given the current installed version is "0.1.0"
    And the latest PyPI version is "0.2.0"
    And auto_update is set to "true" in config
    When I run "teddy update"
    Then the upgrade is executed via pip
    And I see "Updated to v0.2.0."
    And heavy imports are pre-warmed

  Scenario: Newer version available with auto_update=false
    Given the current installed version is "0.1.0"
    And the latest PyPI version is "0.2.0"
    And auto_update is set to "false" in config
    When I run "teddy update"
    Then I see "A new version 0.2.0 is available. Run 'teddy update --yes' to upgrade."

  Scenario: Force upgrade with --yes flag
    Given the current installed version is "0.1.0"
    And the latest PyPI version is "0.2.0"
    And auto_update is set to "false" in config
    When I run "teddy update --yes"
    Then the upgrade is executed via pip
    And I see "Updated to v0.2.0."

  Scenario: Experimental flag uses TestPyPI
    Given the current installed version is "0.1.0"
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
    Then I see "TeDDy v0.1.0"

  Scenario: Display version via version subcommand
    When I run "teddy version"
    Then I see "TeDDy v0.1.0"
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

## Implementation Plan

### Strategy
Use a lightweight utility module in `core/services/update_checker.py` (Option B). No new ports or adapters needed. Extract the pre-warming logic from `__main__.py` into `cli_helpers.py` to avoid duplication. The update command, version flag, and background checks are wired directly into the existing CLI handler functions.

### Key Guidelines
- All HTTP calls use `urllib.request` (stdlib) — no new dependencies.
- Version comparison uses `packaging.version.Version` (already transitive via `pip-audit`).
- Cache file lives at `.teddy/.update_cache.json`.
- Background check runs as a daemon thread in `handle_new_session` and `handle_resume_session`.
- The `update` command is a standalone Typer command in `__main__.py`.
- Pre-warming is extracted to `cli_helpers.prewarm_imports()` and called by both `init` and `update`.

## Deliverables

- [ ] **Contract** - Define `prewarm_imports()` function signature in `cli_helpers.py` (extracted from `__main__.py`).
- [ ] **Harness** - Add `packaging` to test dependencies if not already present (should be transitive; verify).
- [ ] **Harness** - Create test fixture/setup for mocking HTTP responses (PyPI JSON) in unit tests.
- [ ] **Logic** - Implement `src/teddy_executor/core/services/update_checker.py` with all functions.
- [ ] **Logic** - Extract and implement `prewarm_imports()` in `cli_helpers.py`.
- [ ] **Wiring** - Add `--version` to Typer app in `__main__.py`.
- [ ] **Wiring** - Add `version` subcommand in `__main__.py`.
- [ ] **Wiring** - Add `update` command with `--yes` and `--experimental` options in `__main__.py`.
- [ ] **Wiring** - Add background version check call in `session_cli_handlers.py` (in `handle_new_session` and `handle_resume_session`).
- [ ] **Wiring** - Add `auto_update` key to `config.yaml` baseline.
- [ ] **Wiring** - Read `auto_update` config in update command.
- [ ] **Logic** - Update `__main__.py` `init` command to use `prewarm_imports()` from `cli_helpers`.
- [ ] **Test** - Unit tests for `update_checker.py` (version comparison, cache I/O, fetch, upgrade, should_update).
- [ ] **Test** - Unit tests for `prewarm_imports()` extraction (verify it runs without error).
- [ ] **Test** - Acceptance test for `teddy update` happy path.
- [ ] **Test** - Acceptance test for `teddy --version`.
- [ ] **Test** - Acceptance test for `teddy update --experimental`.
- [ ] **Harness** - Create a `FakeHTTPResponse` test helper if needed to simulate PyPI responses.

## Implementation Notes

*(To be filled by Developer)*

## Verification

1. Run `poetry run teddy --version` — should print "TeDDy v0.1.0"
2. Run `poetry run teddy version` — should print same
3. Run `poetry run teddy update` while offline — should print "Could not check for updates: [error]" or fallback silently.
4. Run `poetry run teddy update` with network — should check PyPI and either update or report up-to-date.
5. Run `teddy start` — should start a session. Background check should not delay.
6. Set `auto_update: false` in `.teddy/config.yaml`, run `teddy update` — should show notification only.
7. Run full test suite to ensure no regressions.
