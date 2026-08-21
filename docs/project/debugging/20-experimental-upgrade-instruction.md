# Bug: Experimental Update Path Shows Wrong Command

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** [docs/project/specs/update-checker.md](/docs/project/specs/update-checker.md)

## Symptoms

**Expected Behavior:** When running `teddy update` without `--experimental` flag, if the user is currently on an experimental version (installed from TestPyPI) and a new stable version is available on PyPI, the command should display:
```
uv tool install teddy-cli --force
```

**Actual Behavior:** The command currently displays:
```
uv tool upgrade teddy-cli
```

**Reproduction Steps:**
1. Install an experimental version from TestPyPI (e.g., via the experimental install command).
2. A new stable version is available on PyPI.
3. Run `teddy update` (without `--experimental`).
4. Observe the displayed upgrade command.

## Context & Scope

### Regressing Delta
The notification-only refactor of `__main__.py::update()` (documented as technical debt in `docs/project/PROJECT.md`: "`perform_upgrade` and `should_update` in `update_checker.py` were removed as dead code ... Upgrade instructions now use `uv tool upgrade teddy-cli`") introduced a generic `else` branch that displays a hardcoded `uv tool upgrade teddy-cli` instruction. The pre-existing `is_channel_switch` detection is guarded by `not needs_update`, so it can only fire when the prerelease is NOT strictly older than the latest stable. When the current install is an experimental prerelease AND a strictly newer stable exists (PEP 440: `0.1.5.dev646 < 0.1.5`), `needs_update=True` → `is_channel_switch=False` → control falls into the hardcoded `else` branch. The delta is therefore the missing channel check in the `else` branch, not the version comparison logic.

### Environmental Triggers
- Currently installed version is a pre-release/dev build (installed from TestPyPI using the documented experimental install command).
- A stable release on PyPI is strictly newer than the installed prerelease.
- `teddy update` invoked WITHOUT `--experimental`.

### Ruled Out
- `update_checker.py` functions (`compare_versions`, `fetch_latest_version`, `is_prerelease`, `get_current_version`) — verified correct by unit tests.
- The `--experimental` branch of `update()` — correct for its scenario (full TestPyPI force-install command).
- The existing `is_channel_switch` (`not needs_update`) branch — correct for switching to an older stable channel.
- The startup notification (`_display_update_notification` in `session_cli_handlers.py`) — separate code path; flagged as a same-class systemic finding for the audit phase.

## Diagnostic Analysis

### Causal Model
The `update` command in `__main__.py` compares `current` vs `latest` using `compare_versions` and routes through three branches:
1. **Already latest** — When `not needs_update` and `not is_channel_switch`.
2. **Channel switch** — When `not needs_update` but current is prerelease and latest is stable. Shows `uv tool install teddy-cli --force`.
3. **Normal upgrade** — When `needs_update` (latest > current). Shows `uv tool upgrade teddy-cli`.

The bug is in branch 3: when the user is on a prerelease version (e.g., `0.1.5.dev646` from TestPyPI) and a *higher* stable version exists (e.g., `0.1.5`), `compare_versions` returns `True`, so branch 3 is taken, showing `uv tool upgrade teddy-cli`. But `uv tool upgrade` does not work reliably when switching from a TestPyPI index to PyPI because the original install used `--index-url` with TestPyPI. The correct command is `uv tool install teddy-cli --force`, which forces reinstall from the default index.

The `is_channel_switch` guard only triggers when `not needs_update` (current >= latest), which is only true when the prerelease version is equal to or newer than the latest stable — not when the stable is genuinely newer. This means the channel-switch path is missed in the common case of upgrading from an experimental build to a newer stable release.

### Discrepancies
- The `is_channel_switch` condition is too restrictive: it only triggers when `not needs_update`, missing the case where `needs_update` is True but the user is still coming from an experimental install. (Resolved: identified and reproduced in MRE; fixed and verified via shadow file.)

### Investigation History
1. Read `__main__.py` update command, `update_checker.py`, acceptance tests, and spec. Identified the three-branch logic and the `not needs_update` guard on `is_channel_switch`.
2. Built MRE (initial version failed due to `monkeypatch` fixture misuse). Fixed to use `unittest.mock.patch`.
3. Executed MRE with current `0.1.5.dev646`, latest `0.1.5` (needs_update=True). Output confirmed: `✗ BUG: Upgrade command shown (should be force install)`. The wrong command `uv tool upgrade teddy-cli` is displayed instead of `uv tool install teddy-cli --force`.
4. Git archaeology: the regressing delta is the notification-only refactor of `update()`; the generic `else` branch hardcodes `uv tool upgrade teddy-cli` without checking whether the current install belongs to the TestPyPI experimental channel.
5. Zero-Touch Verification: copied `src/teddy_executor/__main__.py` → `spikes/debug/shadow_main.py`, applied the minimal fix (the `else` branch selects `uv tool install teddy-cli --force` when `is_prerelease(current)` is True), and re-pointed the MRE at the shadow. MRE output: `✓ CORRECT: Force install command shown`.

## Solution

### Root Cause
The `update()` function in `src/teddy_executor/__main__.py` uses three branches to handle version comparison results. The `else` branch (triggered when `needs_update=True`, i.e., latest > current) unconditionally prints `uv tool upgrade teddy-cli`. This is incorrect when the current installed version is a pre-release from the TestPyPI experimental channel (`is_prerelease` returns `True`). `uv tool upgrade` cannot reliably move a tool off a custom index back to PyPI; the correct command is `uv tool install teddy-cli --force`, which forces a reinstall from the default index.

The existing `is_channel_switch` detection only fires when `not needs_update` (current ≥ latest), so it misses the common case where a strictly newer stable version exists.

### Fix (1-line conditional)
In the `else` branch of `update()`, add a guard that checks `is_prerelease(current)` and selects the appropriate command:
- If current is a pre-release → `uv tool install teddy-cli --force`
- Otherwise → `uv tool upgrade teddy-cli`

This ensures that users coming from the experimental channel see the correct force-install command, while normal upgrades continue to show the simpler `uv tool upgrade` command.

### Preventative Measures
1. **Same-class audit:** The startup notification in `_display_update_notification` (`session_cli_handlers.py`) also hardcodes `uv tool upgrade teddy-cli` without a channel check. This should receive the same treatment (logged as technical debt).
2. **Rule-based pattern:** Any upgrade instruction that may involve switching from a TestPyPI install to PyPI must use `uv tool install teddy-cli --force`. A shared helper function could centralize this logic to prevent future drift.
3. **Testing:** The acceptance test `test_experimental_and_dev_update.py` includes a test (`test_dev_version_offers_upgrade_to_stable`) that covers the channel-switch path, but does not cover the case where `needs_update=True` and current is a prerelease. A regression test should be added for this scenario.

### Verified Evidence
- **MRE (unfixed):** `current=0.1.5.dev646`, `latest=0.1.5` → output shows `✗ BUG: Upgrade command shown (should be force install)` → `uv tool upgrade teddy-cli` printed.
- **Shadow verification (fixed):** Same scenario, shadow module with the one-line conditional → output shows `✓ CORRECT: Force install command shown` → `uv tool install teddy-cli --force` printed.
