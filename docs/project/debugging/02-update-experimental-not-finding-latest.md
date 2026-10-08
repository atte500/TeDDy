# Bug: `teddy update --experimental` Not Finding Latest Pre-Release

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

**Expected:** Running `teddy update --experimental` on an install of an experimental build should detect and report the newest published PEP 440 dev pre-release (e.g. `0.1.5.dev646` → newer `x.x.x.devNNN`), pointing the user at the upgrade command.

**Actual:** The command no longer finds the latest experimental (pre-release) version. The user reports: "teddy update --experimental not finding latest version anymore" and clarifies: "latest pre-release (e.g. x.x.x.devxxx) I mean".

**Minimal reproduction:**
1. Install/run an experimental channel build.
2. Run `teddy update --experimental`.
3. Observe that the newest dev pre-release is not reported.

## Context & Scope

### Regressing Delta
**Confirmed — commit `3cfe6f73 fix(update): publish dev pre-releases to PyPI and remove TestPyPI from install commands`** (followed by `e2bf200f chore(ci): rename workflow to remove TestPyPI reference`).

That delta migrated dev pre-release publishing from TestPyPI to **PyPI**: `.github/workflows/publish.yml::publish-dev-to-pypi` now publishes on every successful `CI` `main` run with no `repository-url` (default PyPI target), and the README install commands were stripped of TestPyPI. It did **not** update the `--experimental` index selection in `src/teddy_executor/__main__.py`, which still computes `index_url = TEST_PYPI_URL if experimental else PYPI_URL`. `git log -S "TEST_PYPI_URL" -- src` confirms the constant has been unchanged since its introduction (`322c68f3`, `3338b09d`).

### Environmental Triggers
Requires an installed dev pre-release build and reachable package indexes (the check hits the index JSON API over the network). Empirically observed 2026-10-08:
- **PyPI** `https://pypi.org/pypi/teddy-cli/json`: 61 releases, 44 dev, newest dev `0.1.17.dev1198`, stable `info.version = 0.1.16` — where dev pre-releases actually publish.
- **TestPyPI** `https://test.pypi.org/pypi/teddy-cli/json`: 890 releases (legacy), `info.version = 0.1.16.dev1148` — frozen; no longer receives new builds.

The MRE reproduces this fully in-memory by routing a faked `urllib.request.urlopen` per index (no live network needed).

### Ruled Out
- `compare_versions` / `is_prerelease` PEP 440 parsing (unit-tested; the comparison/channel-switch logic behaves correctly once the correct index is queried).
- `fetch_latest_version` response parsing and `max()` selection (returns the true max of whatever index it is given).
- The `--experimental` → `stable_only=False` plumbing (`test_experimental_and_dev_update.py::test_experimental_flag_uses_stable_only_false`).

## Diagnostic Analysis

### Causal Model
`teddy update --experimental` (`src/teddy_executor/__main__.py::update`):
1. Sets `index_url = TEST_PYPI_URL if experimental else PYPI_URL`.
2. Calls `fetch_latest_version(index_url, stable_only=not experimental)`.
3. `fetch_latest_version` (`core/services/update_checker.py`) reads `data['releases']` from that index and returns `max()` over parsed versions (prereleases filtered only when `stable_only=True`).
4. `compare_versions(current, latest)` decides whether to announce an upgrade.

Since `3cfe6f73`, new dev pre-releases publish to **PyPI**, but `--experimental` still queries the now-frozen **TestPyPI**. Its max version is stale (`0.1.16.dev1148`), so the command compares the user's install against an outdated ceiling: when the user is already at/above that ceiling it wrongly prints "You are already running the latest version (…)"; at best it surfaces an out-of-date version — never the true newest `0.1.17.devNNNN` on PyPI.

### Discrepancies
- README claims experimental versions are published on PyPI, but `__main__.py` queries `TEST_PYPI_URL` for `--experimental`. **(Resolved: the publish workflow moved dev builds to PyPI in `3cfe6f73` while the CLI's index selection was left pointing at TestPyPI — a change missed in the same commit's scope.)**

### Investigation History
1. Hypothesis: pre-release detection lives in the update path. Observation: `__main__.py` selects `TEST_PYPI_URL` for experimental; `update_checker.fetch_latest_version` supports `stable_only=False`. Conclusion: channel selection is the prime suspect; need to confirm the real publish target.
2. Hypothesis: the experimental flag correctly threads `stable_only=False`. Observation: `test_experimental_and_dev_update.py::test_experimental_flag_uses_stable_only_false` asserts it. Conclusion: the flag plumbing is correct; the index target and comparison path remain under investigation.
3. Hypothesis: the wrong index is queried. Observation: live probe — PyPI carries the dev train to `0.1.17.dev1198`; TestPyPI is frozen at `0.1.16.dev1148`. Conclusion: `--experimental` reads a stale index. Confirmed.
4. Hypothesis: a recent change redirected publishing off TestPyPI. Observation: `git log -S` — `3cfe6f73` moved dev publishing to PyPI and renamed the workflow (`e2bf200f`) but left `TEST_PYPI_URL` untouched in `src/`. Conclusion: regressing delta isolated.
5. Hypothesis: querying PyPI (instead of TestPyPI) for `--experimental` resolves the symptom. Observation: the MRE against the real `src/` emitted "You are already running the latest version (0.1.16.dev1148)." and did not report `0.1.17.dev1198` (bug reproduced). The MRE against the shadow replica `spikes/debug/shadow_main.py` — carrying the single-line fix `latest = fetch_latest_version(PYPI_URL, stable_only=not experimental)` — PASSED and reported `0.1.17.dev1198`. Conclusion: fix empirically proven via the Shadow File methodology; the `--experimental` check must target PyPI.

## Solution

### Root Cause

Since commit `3cfe6f73 fix(update): publish dev pre-releases to PyPI and remove TestPyPI from install commands`, TeDDy's dev pre-releases are published to **PyPI**: the `publish-dev-to-pypi` job in [`.github/workflows/publish.yml`](/.github/workflows/publish.yml) builds `${NEXT_VERSION}.dev${run_number}` and publishes with the default PyPI target (no `repository-url`; no TestPyPI job exists). That commit updated the publish workflow and the README, but **left the CLI's `--experimental` channel selection pointing at the retired TestPyPI index**:

```python
# src/teddy_executor/__main__.py::update
index_url = TEST_PYPI_URL if experimental else PYPI_URL
latest = fetch_latest_version(index_url, stable_only=not experimental)
```

TestPyPI is now frozen (`0.1.16.dev1148`, 890 legacy releases) while PyPI carries the live dev train (`0.1.17.dev1198`). Because `--experimental` still reads the frozen index, it compares the user's install against a stale ceiling and either prints "You are already running the latest version (…)" or surfaces an out-of-date version — never the true newest `x.x.x.devNNN`.

### Verified Fix

`--experimental` must query **PyPI** and simply widen the check to include pre-releases:

```python
# Dev pre-releases are published to PyPI (.github/workflows/publish.yml),
# so --experimental only widens the check to include prereleases.
latest = fetch_latest_version(PYPI_URL, stable_only=not experimental)
```

**Evidence (Shadow File methodology — no production code touched):**
- MRE vs. real `src/` → `You are already running the latest version (0.1.16.dev1148).` (bug reproduced).
- Same MRE vs. shadow replica with the one-line fix → `A new experimental version 0.1.17.dev1198 is available.` (fix proven).

### Preventative Measures

**Class:** *a channel/infra migration changed where artifacts are published, but a hardcoded reference to the retired channel was left behind in a consumer, silently reading a frozen source.*

1. **Remove the dead constant.** Delete `TEST_PYPI_URL` from `core/services/update_checker.py` and its import in `__main__.py`, so no code can ever reference the retired channel again. The publish target becomes single-sourced to `PYPI_URL`.
2. **Correct every stale channel reference** surfaced by the systemic audit: the `--experimental` help text (`__main__.py`), the pre-release-install comment (`session_cli_handlers.py`), the `update_checker.py` module/function docstrings, the acceptance-test docstrings, and the component doc [`docs/architecture/core/services/update_checker.md`](/docs/architecture/core/services/update_checker.md).
3. **Pin the behaviour with a regression test.** Rewrite `test_experimental_wiring.py` so it asserts `--experimental` queries `PYPI_URL`, and add a behavioural test proving a newer PyPI dev release is reported — so the channel wiring can never silently regress to a retired index.

### Disposition

**Trivial, localized direct fix.** One production line plus mechanical cleanup of comments/docstrings/tests; no Port, Signature, or DTO changes; single module constant with two consumers. Executed directly via Phase 6 (no Vertical Slice required).
