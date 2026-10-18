# Bug: EDIT Actions Introduce Extra Empty Lines on Windows
- **Status:** Resolved
- **Milestone:** N/A (ad-hoc)
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
On Windows, an EDIT action writes line endings that readers render as extra blank lines. The repository has no byte-exact expected-vs-actual test for `edit_file`, so the drift passes the suite.

Minimal reproduction (emulated Windows write on any host): `spikes/debug/edit-windows-newline-drift/01-edit-windows-newline-drift-mre.py`.

## Context & Scope
### Regressing Delta
Commit 43b7051e made `write_file` newline-deterministic, and commit 6ba37e2b extended the invariant to residual write sites. `LocalFileSystemAdapter.edit_file` was not migrated and still uses the platform-default `newline=None`:
- `edit_file` reads with `Path.read_text(encoding="utf-8")`.
- `edit_file` writes with `Path.write_text(new_content, encoding="utf-8")`.

### Environmental Triggers
Windows. `Path.write_text` with `newline=None` translates every "\n" to `os.linesep` ("\r\n"). Content that already carries CRLF becomes CRLFCRLF, which universal-newline readers render as an extra blank line.

### Ruled Out
- `EditSimulator` CRLF handling: it detects the matched terminator, and a unit test covers CRLF preservation.
- `write_file` and `open_file_for_append`: both pass `newline=""` and have byte-exact tests.
- The `edit_file` read path: unchanged by design. Universal-newline content keeps the simulator's deletion branch valid, because it matches on `"\n" + best_match`.

## Diagnostic Analysis
### Causal Model
1. `edit_file` reads the target with universal newlines, so in-memory content uses LF.
2. `EditSimulator` composes `new_content`.
3. `edit_file` persists `new_content` through `Path.write_text` with `newline=None`.
4. On Windows, step 3 translates every "\n" to "\r\n"; a CRLF already present becomes "\r\r\n".
5. A CRLF clipboard plan leaves a trailing "\r" on every fence block, because the parser strips only "\n" from block content.
6. `create_file` writes through a platform-default text mode, so a CREATE action on Windows translates every LF to CRLF.

### Discrepancies
- [x] `edit_file` violates the byte-exact persistence invariant that `write_file` established. (Resolved: the write now passes `newline=""` and emits the simulated content verbatim.)
- [x] No regression test asserts verbatim expected-vs-actual bytes for `edit_file`. (Resolved: byte-exact LF and CRLF regression tests now cover `edit_file`.)
- [x] The parser extraction of FIND/REPLACE fence content may or may not preserve CRLF from a Windows clipboard plan. (Resolved: the probe showed that mistletoe preserves CRLF in fence content, and the parser returns it in both blocks.)
- [x] `edit_file` reads with `Path.read_text`, whose `newline` parameter requires Python 3.13, while the project supports 3.11. The read fix must use `open(..., newline="")`. (Resolved: the fix stays on the write boundary, so the read constraint no longer applies.)
- [x] The parser strips only `"\n"` from fence content, so a CRLF plan left a trailing `"\r"` on FIND and REPLACE blocks. (Resolved: the parser now normalizes CRLF to LF at plan entry, so fence content and message sections carry no carriage returns.)
- [x] `create_file` wrote through a platform-default text mode, so a CREATE action on Windows could translate LF line endings to CRLF. (Resolved: `create_file` now passes `newline=""` and emits content verbatim.)

### Investigation History
1. Inspected newline handling across the adapter stack; observed `edit_file` uses `newline=None` while `write_file` uses `newline=""`; concluded the EDIT write path escaped the determinism migration.
2. Emulated the Windows write translation in an MRE; observed the plain LF edit persisted as CRLF and a CRLF replacement persisted as `\r\r\n`, which renders as an empty line. The persistence boundary is faulty in isolation.
3. Searched history for `newline=""` in `local_file_system_adapter.py`; observed only commits 43b7051e and 6ba37e2b introduced it, and both target `write_file` and `open_file_for_append`. Observed `write_text(new_content, ...)` arrived in e501c9c6 and never carried the parameter. The EDIT path was never migrated.
4. Checked the runtime and declared support; observed Python 3.13 with `requires-python >=3.11, <3.15`. `Path.write_text` accepts `newline` since 3.10, but `Path.read_text` accepts `newline` only since 3.13. The read fix must use `open(..., newline="")` to stay valid on 3.11 and 3.12.
5. Attempted an end-to-end CRLF plan probe; observed `ModuleNotFoundError: No module named 'tests.harness'` because a plain `uv run python` does not add the repository root to `sys.path`. Added the project root before the import.
6. Reran the end-to-end CRLF plan probe. Observed that mistletoe preserves CRLF in fence content, the parser returns FIND `'second line\r'` and REPLACE `'replacement one\r\nreplacement two\r'`, the simulator keeps the CRLF replacement intact, and the emulated Windows write emitted `b'first line\r\nreplacement one\r\r\nreplacement two\r\r\nlast line\r\n'`. The full clipboard-to-disk chain is verified.
7. Reviewed the read boundary as a fix candidate; observed that `_apply_single_edit` removes deletions via the `"\n" + best_match` match, which assumes universal-newline content. Reading with `newline=""` would expose CRLF content to that branch and can leave a stray `\r`. The fix is therefore scoped to the write boundary.
8. Applied the proven write-boundary fix and added byte-exact regression tests; observed `make test` pass. The EDIT write now emits the simulated content verbatim on every platform.
9. Traced the CREATE dispatch through `ActionFactory` and audited parser tests for carriage-return expectations; observed that CREATE maps to `create_file` and that no test asserts CRLF preservation in parsed plan content.
10. Probed a CRLF clipboard plan against a replica that normalizes CRLF to LF at plan entry; observed the production parser returns FIND `'second line\r'` and REPLACE `'replacement one\r\nreplacement two\r'`, while the replica returns clean LF blocks.
11. Probed `create_file` under an emulated Windows `open` translation; observed the production adapter writes `b'line one\r\nline two\r\n'`, while the replica with `newline=""` writes `b'line one\nline two\n'`.
12. Applied both proven debt fixes to `src/`, added three regression tests, and observed `make test` pass with 1857 passed and 5 skipped.
13. Attempted the first commit gate and observed the pre-existing C901 finding in `parse` (complexity 10 > 9) blocking ruff-lint. Extracted `_normalize_plan_content`, `_is_session_plan`, and `_write_back_session_plan`, then observed `ruff check` pass and `make test` pass with 1857 passed and 5 skipped.
14. Committed the fix as f0ea0335 and pushed to `origin/main`. Observed CI run 39115270282 with the blocking OS matrix green on ubuntu, macos, and windows. The non-blocking Quality Checks job failed the same nine pre-existing steps scheduled in Milestone 5. Triage confirmed the changed files add no new ruff findings. Both production files already exceeded the 300-line gate before the change.

## Solution
### Root Cause Analysis
Three write-boundary defects produced the symptom on Windows.
1. `LocalFileSystemAdapter.edit_file` persisted the simulated content through `Path.write_text` with the platform-default `newline=None`. On Windows, that call translates every LF to CRLF. When a clipboard plan supplies a CRLF replacement, the file receives CRLFCRLF, which universal-newline readers render as an extra blank line.
2. `MarkdownPlanParser.parse` stripped only `"\n"` from fence content, so a CRLF plan left a trailing `"\r"` on FIND and REPLACE blocks. The matcher tolerated it, but the carriage return travelled into the simulator.
3. `LocalFileSystemAdapter.create_file` wrote through a platform-default text mode, so a CREATE action on Windows could translate LF endings to CRLF.

The sandbox replicas proved each fix. `newline=""` on the EDIT and CREATE writes preserves the in-memory bytes exactly, and CRLF-to-LF normalization at plan entry yields clean fence content and message sections.

### Affected Components
- `src/teddy_executor/adapters/outbound/local_file_system_adapter.py`: `edit_file` and `create_file` now write with `newline=""`.
- `src/teddy_executor/core/services/markdown_plan_parser.py`: `parse` normalizes CRLF to LF at plan entry and delegates to `_normalize_plan_content`, `_is_session_plan`, and `_write_back_session_plan` to satisfy the complexity gate.
- `tests/suites/unit/adapters/outbound/test_file_system_adapter_newline_determinism.py`: byte-exact EDIT and CREATE regression tests.
- `tests/suites/unit/core/services/test_parser_crlf_normalization.py`: CRLF plan normalization regression tests.
- Direct upstream callers keep the same signatures and return values. No migration is required.

### Preserved Reproductions
- `spikes/debug/edit-windows-newline-drift/01-edit-windows-newline-drift-mre.py`: minimal Windows write emulation.
- `spikes/debug/edit-windows-newline-drift/02-crlf-plan-to-disk-probe.py`: clipboard plan traced to disk bytes.
- `spikes/debug/edit-windows-newline-drift/03-verify-replica-fix.py`: EDIT write-boundary proof.
- `spikes/debug/edit-windows-newline-drift/04-verify-debt-fixes.py`: parser and CREATE proofs.
