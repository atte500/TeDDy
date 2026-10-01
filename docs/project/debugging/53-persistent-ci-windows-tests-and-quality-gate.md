# Bug: Persistent CI failures on main (Windows tests + pre-commit quality gate)

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

**Expected:** Every push to `main` produces a green CI run.

**Actual:** Four consecutive CI runs failed on `main` on 2026-10-01 (run start times 15:10:50Z → 15:25:50Z), all sharing the same two-job failure signature:

| Run ID | Commit | Subject | Conclusion |
| --- | --- | --- | --- |
| 36882216154 | `a1fe87c3` | feat(session-collision-guard): add sibling-integrity gate | failure |
| 36883318544 | `963d2cda` | feat(windows-startup-latency): return project context from generate_plan | failure |
| 36883483806 | `de56a5bc` | docs(session-collision-guard): mark slice completed after verification | failure |
| 36884189128 | `4e760b44` | feat(cli): accept repeated -c/--context flags with comma-separated compat | failure |
| 36886338394 | `c1edb0fe` | test(windows-startup-latency): add harness fakes for hook-shim state and registry cache | failure |
| 36886417695 | `a6185201` | fix(outbound): replace racy logging.disable toggles with thread-safe counted suppression | failure |
| 36886668346 | `727d79e3` | docs(debugging): require thread-safe counted suppression for logging (follow-up) | failure |

Verified failing jobs/steps (via `gh run view` on 36882216154 and 36884189128):
- `Test Suite (windows-latest)` → step `Run Tests` — exit code 1.
- `Quality Checks` → step `Run Pre-commit Hooks` — exit code 1; downstream steps (`Verify Test Pyramid`, file length, duplication checks) skipped.
- `Test Suite (macos-latest)` and `Test Suite (ubuntu-latest)` pass in every observed run.

Runs for `c1edb0fe` and two newer commits on `origin/main` (`a6185201` — "fix(outbound): replace racy logging.disable toggles…", `727d79e3` — "docs(debugging): require thread-safe counted suppression…") all concluded **failure** with the identical two-job signature — the breakage persists on the current tip of `origin/main`, which has advanced beyond the local checkout (sync pending before any fix).

**Minimal reproduction:** Push any commit to `main` — including a docs-only commit (`de56a5bc` touched only Markdown) — and both jobs fail identically.

## Context & Scope

### Regressing Delta
CONFIRMED: commit `a1fe87c3` — "feat(session-collision-guard): add sibling-integrity gate for exclusive session claims" (parent `1c70b755`, whose CI run 36881833988 concluded `success` — the boundary is directly observed, not inferred). Its only code change is +140 lines in `tests/suites/integration/core/services/test_session_service.py` (verified via `git show --name-only`; the earlier unit/integration ambiguity was a log-rendering truncation artifact), including the now-failing `test_turn_100_migration_claims_unoccupied_root_and_preserves_sibling`. The failure is a test-encoded contract (byte-exact ledger persistence across turn-100 migration) colliding with a pre-existing platform I/O property (text-mode newline translation in the filesystem adapter) that only manifests on Windows.

### Environmental Triggers
- GitHub Actions `windows-latest` runner for the failing test suite.
- `Quality Checks` job — runner OS to be confirmed from `.github/workflows/ci.yml`.
- Failure is committed-state-persistent: survives four commits, including a docs-only commit.
- Verification state: the RPP probe commit (`b8610d29`, touching only `spikes/debug/`) is the current tip of `origin/main` and of the local checkout; it triggers the same expected-RED CI run (known noise until the fix lands). Case File 53 and `spikes/debug/probe_output.txt` remain untracked pending the Alignment gate.

### Ruled Out
- Commits `963d2cda`, `de56a5bc`, `4e760b44` as the introducing delta (they post-date the first failure).
- Transient infrastructure flakiness (identical signature across 4 runs spanning ~15 minutes; docs-only commit fails).
- macOS and ubuntu test runners (consistently green).
- Local workspace state (working tree clean and synced to `origin/main`).
- Quality Checks hook failures (ruff-format / Mypy / pip-audit) as the run-blocking cause — the job runs with `continue-on-error: true`, so its failures cannot determine the run conclusion.

## Diagnostic Analysis

### Causal Model
The run-blocking failure is the Windows test suite alone: the `quality-checks` job has `continue-on-error: true` in ci.yml, so its failures do not affect the run conclusion. Within the Windows leg, exactly one test fails deterministically: `test_turn_100_migration_claims_unoccupied_root_and_preserves_sibling` (`tests/suites/integration/core/services/test_session_service.py:176`), with `AssertionError: assert b'README.md\r\n' == b'README.md\n'`.

**Verified mechanism (root cause):** commit `a1fe87c3` introduced this test, which encodes a byte-exact persistence contract for the turn-100 migration. The migration's copy path `_clone_session_artifacts` (`session_service.py`) copies `session.context` via `IFileSystemManager.read_file` → `write_file`. `LocalFileSystemAdapter` implements both with default text-mode I/O (`read_text` / `write_text`, no `newline` argument): reads normalize every line ending to `\n` in memory (universal newlines), writes translate `\n` → `os.linesep` (`\r\n` on Windows). Full causal chain on Windows: (1) the test's Arrange writes `session.context` via `write_text(..., encoding="utf-8")` → disk holds `README.md\r\n`; (2) the migration round-trip (read-normalize → write-translate) re-emits `\r\n` into the claimed copy; (3) the hardcoded byte assertion `b"README.md\n"` fails. On POSIX no write-side translation occurs, so disk bytes remain `\n` and the test passes. A repo-wide grep confirms zero `newline=` control and zero binary file I/O anywhere in `src/` — the adapter is the sole newline authority and it is platform-dependent. Crucially, a test-setup-only fix (fixtures written via `write_bytes`) does NOT resolve the failure: the migration's write side would still translate the normalized `\n` back to `\r\n` on Windows. A production-side change in the adapter's write I/O (newline-deterministic writes, e.g. `newline=""`) or a byte-exact copy operation is mandatory.

**Fix verification (zero-touch, RPP-proven):** a Shadow File replica of `LocalFileSystemAdapter` whose `write_file` passes `newline=""` to `Path.write_text` was verified on windows-latest via the remote probe: with the shadow adapter wired into `SessionService`, the byte-identical turn-100 migration scenario passes byte-exactly (`session.context` copied as `b"README.md\n"`) where the real adapter reproduces the CRLF corruption and the exact CI failure. With `newline=""`, all adapter writes become newline-deterministic (LF-verbatim) on every OS; since all read paths normalize via universal newlines, internal behavior on POSIX is unchanged (verified by the ubuntu control leg and the full local suite passing pre-probe). Blast radius (18 `write_file` call sites across 9 files) covers only TeDDy-internal text persistence: session ledger, planning artifacts, init templates, prompts, lifecycle reports, and the orchestrator temp plan — no user project files written via `create_file`/`edit_file` (those use separate I/O paths).

Quality Checks leg (non-blocking, pre-existing debt, does NOT affect run conclusions): three hooks fail — ruff-format (3 files: `test_tui_editor_flush_outside_suspend.py`, `test_tui_editor_process_group_restoration.py`, `test_tui_editor_suspend_resume.py` — confirmed locally via `ruff format --check`), Mypy (18 errors in 10 files; superset of the debt documented in PROJECT.md), pip-audit (36 vulnerabilities; documented as blocked on upstream litellm). Because the job is `continue-on-error`, these pre-date `a1fe87c3` in effect: the parent commit's `success` run is fully consistent with internally failing hooks. Tracked as existing Technical Debt (Milestone 5), not part of this bug's run-blocking failure.

### Discrepancies
- Overall run conclusion is `failure` although the failing `Quality Checks` job is configured with `continue-on-error: true`. Conflict: the job should not fail the run. (Resolved: ci.yml applies continue-on-error only to quality-checks; the run-blocking failure is the windows-latest test matrix leg.)
- PROJECT.md documents pre-existing Mypy/pip-audit failures that require local `--no-verify`, yet CI was assumed green immediately before `a1fe87c3`. Conflict: the Quality Checks job should have been failing before the boundary too. (Resolved: quality-checks is non-blocking, so the parent commit's run 36881833988 legitimately concluded `success` while its hooks failed internally; the run conclusion never depended on the Quality Checks leg.)
- The failing test lives in `tests/suites/integration/...`, while the `a1fe87c3` stat output appeared to modify `tests/suites/unit/...`. Conflict: the boundary delta may not contain the failing test. (Resolved: `git show a1fe87c3 --name-only` confirms the delta modified `tests/suites/integration/core/services/test_session_service.py`; the apparent unit path was log-rendering truncation.)
- The test's byte-identity contract fails although the migration "copies" the file. Conflict: a faithful copy should preserve bytes. (Resolved: the copy routes through text-mode adapter I/O — `read_text` normalizes to `\n` in memory, `write_text` re-translates to `\r\n` on Windows — so byte-exactness is structurally unfulfillable through the current adapter.)

### Investigation History
1. Hypothesis: the CI failure is tied to the newest commit's delta. Observation: four consecutive failures spanning a docs-only commit. Conclusion: persistent, inherited breakage — not delta-local to the newest commit.
2. Hypothesis: the runs fail for unrelated/flaky reasons. Observation: identical two-job failure signature in the first (36882216154) and latest (36884189128) failed runs. Conclusion: a single persistent failure pair.
3. Hypothesis: the failures are delta-local content regressions. Observation: extracted logs show the Windows job failing exactly one test (`test_turn_100_migration_claims_unoccupied_root_and_preserves_sibling`, CRLF byte assertion; 1234 passed, 25 skipped) and Quality Checks failing three hooks (ruff-format: 3 files reformatted; Mypy: 18 errors/10 files; pip-audit: 36 vulns matching documented debt). Conclusion: Windows failure is a single deterministic platform-specific test; Quality Checks failures match the documented pre-existing debt profile and are non-blocking (continue-on-error).
4. Hypothesis: current HEAD (`c1edb0fe`) is also affected. Observation: run 36886338394 concluded failure with the identical two-job signature. Conclusion: the failure persists on latest `main`; HEAD is affected.
5. Hypothesis: the failing test was introduced by `a1fe87c3`. Observation: `git show a1fe87c3 --name-only` confirms the delta modified `tests/suites/integration/core/services/test_session_service.py`; the parent commit `1c70b755`'s CI run (36881833988) concluded `success`. Conclusion: boundary directly observed; the failing test is the regressing delta.
6. Hypothesis: the migration copy path is byte-exact (binary I/O), making the defect test-only. Observation: `_clone_session_artifacts` copies via `read_file`/`write_file`; `LocalFileSystemAdapter` uses default text-mode `read_text`/`write_text` with no `newline` argument; repo-wide grep finds no newline control or binary I/O in `src/`. Conclusion: the copy path translates newlines on Windows; the test's byte-identity contract is unfulfillable through text-mode adapter I/O — a production-side change is mandatory.
7. Hypothesis: a test-setup-only fix (fixtures written via `write_bytes`) would suffice. Observation: with LF bytes on disk, the adapter read normalizes to `\n` in memory and the write side re-translates to `\r\n` on Windows, so the copied file still ends with `\r\n`. Conclusion: rejected — write-side translation alone defeats byte-exactness; the fix must target the adapter's I/O semantics.
8. Hypothesis: the shadow fix (`newline=""` on `write_file`) resolves the byte-exactness failure while the real adapter reproduces it, and the RPP probe is mechanically sound. Observation (local macOS control run of `spikes/debug/probe.sh`): LEG 0 both writes `b'line\n'` (no POSIX translation); LEG 0b real and shadow `write_file` both emit `b'line\n'`; LEG A (exact CI-failing test) PASS; LEG B (same scenario via shadow adapter) PASS; exit 0. Conclusion: probe plumbing validated end-to-end; POSIX control matrix matches predictions; the discriminating Windows evidence requires the remote cycle on windows-latest.
9. Hypothesis: the shadow `newline=""` fix resolves the byte-exactness failure on the failing platform. Observation (RPP run via `debug.yml`, workflow_dispatch): On **windows-latest** — LEG 0: default `write_text` → `b'line\r\n'`, `newline=""` → `b'line\n'`, `os.linesep == '\r\n'`; LEG 0b: real adapter `write_file` → `b'line\r\n'`, shadow adapter → `b'line\n'`; LEG A: the exact CI-failing test FAILS with the identical assertion (`AssertionError: assert b'README.md\r\n' == b'README.md\n'`, "At index 9 diff: b'\r' != b'\n'" at `test_session_service.py:176`); LEG B: the byte-identical scenario wired with the shadow adapter via constructor injection PASSES. On **ubuntu-latest** (control): all-LF matrix, LEG A PASS, LEG B PASS. Conclusion: root cause mechanism empirically confirmed AND the `newline=""` fix empirically proven zero-touch on windows-latest via the Shadow File methodology — no `src/` or `tests/` modification was required for verification.
10. Hypothesis: the approved `write_file`-scoped fix covers the entire defect category ("platform-dependent default text-mode I/O on a persistence path carrying a byte-exact contract"). Observation (Systemic Audit sweep, on tip `3f4ccbf7`): `create_file` has zero internal callers (port + adapter definitions only — user-facing mutation flows elsewhere, preserving the approved round-trip scope); `open_file_for_append` is used only by internal session-log appenders (`session_lifecycle_manager.py:124`, `session_orchestrator.py:220`) with no byte-exact contracts; direct `write_text` sites outside the adapter are `context_service.py:447` and `update_checker.py:193` (JSON caches — newline-insensitive) and `markdown_plan_parser.py:135` (plan rewrite); zero `os.linesep` reliance in `src/` and `tests/`; origin-sync diff confirms no fix-surface file was touched by the three incoming commits. Conclusion: no internal byte-exact persistence contract exists outside `write_file`; the one-line adapter fix covers the entire run-blocking defect class; residual platform-dependent write sites are logged as Technical Debt for a Milestone 5 newline-determinism sweep.

## Solution

**Root cause (high-level):** Commit `a1fe87c3` introduced the first test encoding a byte-exact persistence contract through the session migration's copy path. That copy routes through `LocalFileSystemAdapter.read_file` → `write_file`, which uses default text-mode I/O with no `newline` control: reads normalize all line endings to `\n` in memory (universal newlines), writes translate `\n` → `os.linesep` (`\r\n` on Windows). On Windows the migrated `session.context` therefore holds `README.md\r\n` while the test asserts byte-exact `README.md\n`; on POSIX no write-side translation occurs, which is why macOS/ubuntu stayed green. The adapter is the sole newline authority in the system and its behavior was platform-dependent — a latent defect exposed, not caused, by the new contract.

**Proven fix (user-approved Option A, scoped to `write_file` only):** `LocalFileSystemAdapter.write_file` passes `newline=""` to `Path.write_text`, making every internal write newline-deterministic (LF-verbatim) on all platforms. Verified zero-touch on windows-latest via the RPP Shadow File probe (LEG B: byte-identical migration scenario passes byte-exactly with the shadow adapter; LEG A: real adapter reproduces the exact CI failure; ubuntu control leg unchanged). Blast radius (18 `write_file` call sites across 9 files) covers only TeDDy-internal text persistence (session ledger, planning artifacts, init templates, prompts, lifecycle reports, orchestrator temp plan); `create_file`/`edit_file` deliberately keep platform round-trip semantics so user project files never receive whole-file line-ending rewrites (an `edit_file` with `newline=""` would rewrite entire CRLF user files as LF).

**Preventative measures (class-level):**
1. **Regression test in the blocking CI matrix:** the byte-exact turn-100 migration contract itself now guards the fix on windows-latest — any reintroduction of platform-dependent write translation fails CI deterministically.
2. **Single newline authority invariant:** all TeDDy-internal persistence MUST flow through `write_file` (newline-deterministic). The Systemic Audit confirmed this holds today; residual direct `write_text` sites (`context_service.py`, `update_checker.py`, `markdown_plan_parser.py`) carry no byte contracts and are tracked as Technical Debt for a Milestone 5 sweep.
3. **Architecture law extended:** the existing "explicitly specify utf-8" encoding standard is completed by the newline-determinism rule — file writes on persistence paths must be platform-agnostic in BOTH encoding and line endings. Session ledgers are now byte-portable across operating systems.
4. **Contract-first byte fidelity:** any future feature relying on deterministic bytes (hashing, diffing, checksums of ledger files) must assert byte-exactness in the cross-platform test matrix, which now runs on Windows.
