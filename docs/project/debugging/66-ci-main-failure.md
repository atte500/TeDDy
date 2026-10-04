# Bug: CI test failures on main after editor tilde/basename change

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
Expected: `CI` workflow on `main` is green.
Actual: The last two `CI` runs are red — `37118833449` (sha 3b49680) and `37119160343` (sha daa041e). The last green run was `37118255538` (sha cd2e7a9), followed by green `37118201503` (sha f970a31).

## Context & Scope
### Regressing Delta
Confirmed candidate: commit `a97d621a` ("fix(editor): persist basename and expand tilde paths") — the only code commit between the last green run (cd2e7a9) and the first failing run (3b49680). It added the tilde-expansion line `parts[0] = os.path.expanduser(parts[0])` to `ConsoleToolingHelper._resolve_editor_cmd` (`console_tooling.py`) and the new test `tests/suites/unit/adapters/inbound/test_editor_value_persistence.py::test_resolve_editor_cmd_expands_tilde_path`. It also changed `_prompt_for_editor_selection` to persist the basename.

### Environmental Triggers
Platform-specific: FAILS ONLY on `windows-latest`. ubuntu-latest and macos-latest PASS. Python 3.14, pytest-9.1.1, 4 xdist workers.

### Ruled Out
N/A

## Diagnostic Analysis
### Causal Model
Commit a97d621a added `parts[0] = os.path.expanduser(parts[0])` inside `ConsoleToolingHelper._resolve_editor_cmd` AND added the test `test_editor_value_persistence.py::test_resolve_editor_cmd_expands_tilde_path`. The test fails ONLY on windows-latest:

  AssertionError: assert None == ['C:\\Users\\runneradmin/bin/myeditor']

Root cause (mechanism candidate ii — CONFIRMED): the defect is TEST-side cross-platform fragility, NOT a production defect. `mock_env` is a `POSIXPathMock`; its `__call__`/`_normalize_args` (`tests/harness/setup/mocking.py`) rewrites the first string argument of EVERY mock call, replacing `\` with `/`. On Windows:
  1. The test baseline `expanded = os.path.expanduser("~/bin/myeditor")` yields `C:\Users\runneradmin/bin/myeditor` (the home component keeps its backslash).
  2. `_resolve_editor_cmd` computes the IDENTICAL `parts[0]`, but when it calls `self._system_env.which(parts[0])`, `POSIXPathMock.__call__` normalizes that argument to `C:/Users/runneradmin/bin/myeditor` BEFORE invoking the side_effect.
  3. The side_effect's raw equality `name == expanded` → `"C:/Users/..." == "C:\Users/..."` → False → returns `None` → `which` returns `None` → `_resolve_editor_cmd` returns `None`.

On POSIX the expanded path contains no backslash, so normalization is a no-op and the test passes — hence Windows-only. Production `_resolve_editor_cmd` is CORRECT (it expands the tilde before `which`); the fix must be applied to the TEST's side_effect comparison.

Blast radius (confirmed by the Turn-10 census): exactly TWO tests share the fragile raw-equality `which.side_effect` idiom — `test_editor_value_persistence.py::test_resolve_editor_cmd_expands_tilde_path` and `test_diff_tool_tilde_expansion.py::test_teddy_diff_tool_tilde_path_is_expanded` (plus its `_preserves_arguments` sibling). Fix: compare the incoming argument against the harness-normalized (POSIX) form of the resolved path inside each side_effect. Verified zero-touch via the shadow replicas: under a simulated Windows `expanduser`, both real tests FAIL and both shadow fixes PASS (no `src/` or `tests/` files were modified).

### Discrepancies
- Observed: production `_resolve_editor_cmd("~/bin/myeditor")` returned None on Windows. Conflicts with the assumption that test and production call the identical `os.path.expanduser(...)`. (Resolved: they DO call the identical function and produce the identical string; the divergence is injected by `POSIXPathMock`, which normalizes the argument handed to the mocked `which` from `\` to `/`, silently breaking the side_effect's raw equality check. Production is correct.)

### Investigation History
1. Gathered CI run list + recent git log; isolated a97d621a as the regressing candidate. No exact failing step.
2. Extracted the windows-latest job log; found the single failing test `test_editor_value_persistence.py::test_resolve_editor_cmd_expands_tilde_path` with `assert None == ['C:\\Users\\runneradmin/bin/myeditor']`. 1523 passed, 29 skipped, 1 failed. Confirms Windows-only regression introduced by a97d621a's tilde test/behavior.
3. Read the committed `console_tooling.py` (expansion logic matches the diff; imports are real `os`/`shlex`), `POSIXPathMock` (first str arg normalized `\`→`/`), and Case File 64. Re-derived the failure from the exact CI assertion: the mock-normalized argument no longer equals the raw backslash baseline → `which` returns None → `_resolve_editor_cmd` returns None. Root cause CONFIRMED as TEST-side. Pending empirical MRE confirmation.
4. MRE `spikes/debug/66-editor-tilde-windows-mre.py` reproduced the failure on POSIX (raw-equality matcher → None) and verified the normalized matcher → `['C:\\Users\\runneradmin/bin/myeditor']`. Census (Turn 9) found the sibling `test_diff_tool_tilde_expansion.py` uses the SAME fragile raw-equality `which.side_effect` pattern (`resolved = os.path.expanduser("~/bin/mydiff")`); most other `side_effect` sites use relative POSIX-style paths (`.teddy/...`) and are unaffected. Scoping the complete Windows failing set at the latest red commit (daa041ee) pending.
5. Turn 10 census (definitive): only TWO fragile raw-equality `which.side_effect` sites exist — `test_editor_value_persistence.py:59` and `test_diff_tool_tilde_expansion.py:30`. Every other `which`/`get_env` side_effect matches bare editor/env names (`nvim`, `code`, `VISUAL`, `TEDDY_DIFF_TOOL`) or relative POSIX paths (`.teddy/...`) containing no backslash, so `POSIXPathMock` normalization is a no-op and they are unaffected. Blast radius = exactly those two tests. The parallel attempt to extract run 37119160343's windows-latest summary failed (grep no-match on the retrieved log), so HEAD's two-test failure set is established by code reading + the confirmed mechanism rather than by the CI log.
6. Shadow verification (Zero-Touch, Turn 11): created replicas of BOTH faulty TEST files in `spikes/debug/` (`shadow_test_editor_value_persistence.py`, `shadow_test_diff_tool_tilde_expansion.py`) with ONLY the fragile `which` side_effect changed to compare against the harness-normalized (POSIX) form. The rewired MRE drove the REAL tests and the SHADOW replicas under a simulated Windows `os.path.expanduser` (`C:\Users\runneradmin/...`), yielding: `real_editor -> FAIL`, `real_diff -> FAIL`, `shadow_editor -> PASS`, `shadow_diff -> PASS` (`SHADOW OK`). This empirically confirms both (a) that the two real tests reproduce the Windows-only failure and (b) that the normalized-comparison fix makes both pass — WITHOUT touching `src/` or `tests/`. The fix is proven; awaiting user alignment.

## Solution

### Root Cause (verified)

The red CI on `main` is **not a production defect**. Production `ConsoleToolingHelper._resolve_editor_cmd` correctly expands a leading `~` (Bug 64's fix) and is untouched by this repair. The failure is **test-side cross-platform fragility**, introduced together with the editor tilde work by commits `a97d621a` (editor test) and `daa041ee` (diff-tool test).

Both new regression tests verify the resolved command by configuring a `POSIXPathMock` `which` side-effect that compares the incoming path with **raw string equality** against an `os.path.expanduser`-derived baseline:

```python
mock_env.which.side_effect = lambda name: expanded if name == expanded else None
```

`POSIXPathMock.__call__` -> `_normalize_args` (`tests/harness/setup/mocking.py`) rewrites the first string argument of EVERY mock call, replacing `\` with `/`, **before** the side_effect runs. On Windows:

1. `expanded = os.path.expanduser("~/bin/myeditor")` = `C:\Users\runneradmin/bin/myeditor` — the `%USERPROFILE%` component keeps its backslash.
2. `_resolve_editor_cmd` computes the identical string, but its `self._system_env.which(parts[0])` call is intercepted by `POSIXPathMock`, which normalizes the argument to `C:/Users/runneradmin/bin/myeditor`.
3. The side_effect's raw `==` fails (`"C:/Users/..." != "C:\Users/..."`), so `which` returns `None`, and the test fails with `assert None == ['C:\\Users\\runneradmin/bin/myeditor']`.

On POSIX the expanded path contains no backslash, so normalization is a no-op and the tests pass — hence the failure is **windows-latest-only**.

### Proven Fix (test-side only, zero-touch verified)

Compare the incoming (already harness-normalized) argument against the **normalized** form of the resolved path:

```python
normalized = expanded.replace("\\", "/")
mock_env.which.side_effect = lambda name: expanded if name == normalized else None
```

Applied at exactly two sites (the confirmed blast radius):

- `tests/suites/unit/adapters/inbound/test_editor_value_persistence.py::test_resolve_editor_cmd_expands_tilde_path`
- `tests/suites/unit/adapters/outbound/test_diff_tool_tilde_expansion.py::_helper_with_diff_tool`

Production `src/` was NOT touched. Shadow replicas of both test files (`spikes/debug/shadow_test_*.py`) carrying only this change produced `SHADOW OK`: under a simulated Windows `os.path.expanduser`, `real_editor -> FAIL`, `real_diff -> FAIL`, `shadow_editor -> PASS`, `shadow_diff -> PASS`.

### Verification

- **MRE** (`spikes/debug/66-editor-tilde-windows-mre.py`): reproduced the raw-equality collision on POSIX and confirmed the normalized matcher resolves to `['C:\\Users\\runneradmin/bin/myeditor']`.
- **Shadow (zero-touch)**: real tests FAIL ×2; fixed replicas PASS ×2 — proving the fix without modifying `src/` or `tests/`.
- **Post-fix integration**: the corrected tests are re-verified under the simulated Windows `expanduser` (both PASS) and the full suite runs green.

### Systemic Preventative Measure

`ARCHITECTURE.md`'s "Cross-Platform Path Assertions" directive mandates `POSIXPathMock.find_call_by_path` for path **assertions** but prescribes **no idiom** for path-matching **side-effects** — precisely the gap that produced this Windows-only failure. Logged as `[DEBT]` in `docs/project/PROJECT.md`; the candidate durable cure is a single-sourced `normalize_path(value)` helper in `tests/harness/setup/mocking.py` (so `_normalize_args` and every path-matching side-effect share one normalization) plus a note in the cross-platform directive that path-matching side-effects MUST compare against it. Retired directly on 2026-10-04: a single-sourced `mocking.to_posix_path(value)` helper now backs `_normalize_args`, `find_call_by_path`, and every path-matching side-effect, and the `ARCHITECTURE.md` cross-platform directive was extended to mandate it for path-matching side-effects.
