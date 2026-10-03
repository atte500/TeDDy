# Bug: ci-windows-shell-adapter-interrupt
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
**Expected:** CI `test-suite` passes on all three OS legs (ubuntu-latest, macos-latest, windows-latest).

**Actual:** The `Test Suite (windows-latest)` leg fails in the `Run Tests` step (`uv run pytest`). Exactly one test fails:

```
tests/suites/unit/adapters/outbound/test_shell_adapter_interrupt.py::test_await_process_terminates_group_and_reports_interrupt
AttributeError: <module 'os' (frozen)> has no attribute 'killpg'
tests\suites\unit\adapters\outbound\test_shell_adapter_interrupt.py:44
```

Result line: `1 failed, 1466 passed, 28 skipped in 49.70s`. The `ubuntu-latest` and `macos-latest` legs both pass.

**Minimal reproduction steps:** Run `uv run pytest tests/suites/unit/adapters/outbound/test_shell_adapter_interrupt.py::test_await_process_terminates_group_and_reports_interrupt` on a Windows host (e.g. GitHub Actions windows-latest). It passes on POSIX hosts.

## Context & Scope
### Regressing Delta
Prime candidate is the Bug-58 "q-interrupt" commit. Bounding from CI run history:
- Last GREEN run: `37110279374` (2026-10-03 08:36) — `docs: present comma-separated -c as alternative…`.
- First RED run: `37110320149` (2026-10-03 08:37) — `fix(session): interrupt in-flight action on q and persist the quit-key…`.

**Confirmed.** `git log -S "killpg"` and the file history show the sole commit touching `tests/suites/unit/adapters/outbound/test_shell_adapter_interrupt.py` is `b0a18211 fix(session): interrupt in-flight action on q and persist the quit-key reader` (the Bug-58 q-interrupt work — the first RED run `37110320149`). That commit added the entire test file, whose POSIX branch unconditionally executes `monkeypatch.setattr(os, "killpg", ...)` with no platform guard (line 44). Production `ShellAdapter._terminate_process_group` correctly guards `os.killpg` behind `sys.platform != "win32"`; only the TEST seam is Windows-unsafe.

### Environmental Triggers
- **OS:** Windows only (`os.killpg` does not exist on Windows).
- **Runtime:** Python 3.14.7, pytest 9.1.1, pytest-xdist with 4 workers.
- The failing test fails during SETUP (monkeypatch), before production code executes.

### Ruled Out
- `quality-checks` job: non-blocking (`continue-on-error: true`); not the cause of a red required check.
- `ubuntu-latest` and `macos-latest` `test-suite` legs: both green.
- All other 1466 passing tests on the windows leg: green.

## Diagnostic Analysis
### Causal Model
`ShellAdapter._await_process` slices the child wait by polling the injected `InterruptGuard`. When `guard.interrupted.is_set()` is true it calls `ShellAdapter._terminate_process_group(process)`, which branches on the host platform:
- **POSIX** (`sys.platform != "win32"`): `os.killpg(process.pid, signal.SIGKILL)` — the child was launched into its own session/process group via the `preexec_fn` `os.setsid()`, so its pgid equals its pid and `killpg` reaches the whole tree.
- **Windows** (`sys.platform == "win32"`): `process.kill()` (no POSIX process-group equivalent).

Production is correct: `os.killpg` is referenced ONLY inside the POSIX branch, so it is never evaluated on Windows.

The defect is in the unit test `test_await_process_terminates_group_and_reports_interrupt`. It validates only the POSIX branch and unconditionally runs `monkeypatch.setattr(os, "killpg", lambda ...)`. `pytest.monkeypatch.setattr` defaults to `raising=True`, so it calls `hasattr(target, name)` first and raises `AttributeError: <module 'os' (frozen)> has no attribute 'killpg'` when the symbol is absent. On Windows `os.killpg` does not exist, so the test dies in SETUP (line 44) before the SUT executes; on POSIX the symbol exists and the test passes. Hence the windows-latest-only RED and the green ubuntu/macos legs.

### Discrepancies
- The test passes on POSIX and fails on Windows. Conflict: a unit test that patches a module attribute should behave uniformly across platforms. (Resolved: `os.killpg` is POSIX-only; `pytest.monkeypatch.setattr` with its default `raising=True` raises `AttributeError` when the target attribute is absent on the host, so the test's SETUP fails on Windows before the SUT runs. The test seam, not the production code, is the defect.)

### Investigation History
1. Hypothesis: CI failure is in the blocking `test-suite` matrix. Observation: windows-latest leg fails `Run Tests`; ubuntu/macos pass. Conclusion: Windows-specific defect.
2. Hypothesis: the failing test patches a POSIX-only symbol. Observation: `AttributeError: <module 'os' (frozen)> has no attribute 'killpg'`. Conclusion: likely a test-seam portability defect; pending code read.
3. Hypothesis: `test_shell_adapter_interrupt.py` unconditionally patches a POSIX-only `os` attribute. Observation: line 44 executes `monkeypatch.setattr(os, "killpg", ...)` with no platform guard, while `ShellAdapter._terminate_process_group` guards `os.killpg` behind `sys.platform != "win32"`; `git log -S "killpg"` + file history attribute the sole touch to `b0a18211` (Bug-58). Conclusion: production is platform-correct; the test seam is Windows-unsafe. Fix must make the interrupt test platform-portable (POSIX `killpg` branch + Windows `process.kill()` branch) so it is deterministic on every leg.
4. Hypothesis (Zero-Touch verification): the sibling convention `if sys.platform == "win32": pytest.skip("killpg is POSIX only")` neutralizes the failure. Observation (local, emulated Windows by deleting `os.killpg` and setting `sys.platform="win32"`; `src/` and `tests/` untouched): the MRE (`spikes/debug/61-windows-killpg-mre.py`) reproduced the exact `AttributeError: <module 'os' (frozen)> has no attribute 'killpg'` AND then verified the SUT's Windows path terminates the child via `process.kill()` (`interrupted=True`, `kill_calls=1`, no `os.killpg` reference); the shadow ORIGINAL test (`spikes/debug/test_shadow_original_shell_adapter_interrupt.py`) failed with the identical CI `AttributeError`; the shadow FIXED test (`spikes/debug/test_shadow_fixed_shell_adapter_interrupt.py`) skipped cleanly (exit 0). Conclusion: root cause and the guard fix are empirically proven without touching production/test code. The fix is two lines in the failing test: add `import sys` and the `if sys.platform == "win32": pytest.skip(...)` guard. (Orchestration note: the initial single-shell EXECUTE aborted after the expected-RED exit code under errexit; re-running with `set +e` observed both stages.)

## Solution

**Root cause (test-seam portability defect, not a production defect).** The unit test `tests/suites/unit/adapters/outbound/test_shell_adapter_interrupt.py` (added whole by `b0a18211`, the Bug-58 q-interrupt work) monkeypatched the POSIX-only symbol `os.killpg` unconditionally:

```python
monkeypatch.setattr(os, "killpg", lambda pid, sig: killed.append((pid, sig)))
```

`pytest`'s `monkeypatch.setattr` defaults to `raising=True`, i.e. it first calls `hasattr(os, "killpg")`. On Windows the symbol does not exist, so the test fails in SETUP with `AttributeError: <module 'os' (frozen)> has no attribute 'killpg'` before any production code runs. On POSIX (Linux/macOS) the symbol exists, so the test passes — hence the windows-latest-only RED with green ubuntu/macos legs.

Production `ShellAdapter` was never at fault: it references `os.killpg` ONLY inside its `sys.platform != "win32"` branch (`_handle_timeout`, `_terminate_process_group`) and falls back to `process.kill()` on Windows.

**Fix (test-only, 3 lines).** Make the interrupt test platform-portable by guarding the POSIX-only assertion, mirroring the direct sibling that exercises the identical `killpg` termination path (`test_shell_adapter_timeout.py`):

```python
import sys

import pytest
# ...
def test_await_process_terminates_group_and_reports_interrupt(monkeypatch):
    if sys.platform == "win32":
        pytest.skip("killpg is POSIX only")
    ...
```

This turns the windows-latest RED into a deterministic skip while preserving full POSIX coverage (where process-group termination semantics actually apply). No production code changes.

**Evidence (Zero-Touch Verification — `src/` and `tests/` untouched).** Emulating the single Windows condition (`os.killpg` deleted, `sys.platform="win32"`):
- `spikes/debug/61-windows-killpg-mre.py` reproduced the exact `AttributeError` AND verified the SUT's Windows path terminates the child via `process.kill()` (`interrupted=True`, `kill_calls=1`, zero `os.killpg` references).
- `spikes/debug/test_shadow_original_shell_adapter_interrupt.py` → `1 failed` with the identical CI `AttributeError` (local RED).
- `spikes/debug/test_shadow_fixed_shell_adapter_interrupt.py` → clean SKIP (`GREEN exit=0`).

**Preventative measures (systemic).** The defect class is "a test seam patches a POSIX-only `os`/`signal` symbol without a platform guard". The Systemic Audit census confirmed this is the ONLY current instance (the `os.kill` sites in `test_terminal_quit_key_listener_reader.py` are Windows-safe; all production POSIX references are guarded). Prevention:
1. Adopt the established in-body `if sys.platform == "win32": pytest.skip(...)` / `pytest.mark.skipif(...)` idiom for every test that patches a POSIX-only symbol (precedent: `test_shell_adapter_timeout.py`, `test_shell_adapter_granular_failure.py`).
2. Candidate poka-yoke check (logged as `[DEBT]`) to flag unguarded `monkeypatch.setattr(os, "<posix_only>")` / `patch("os.<posix_only>")` in `tests/`.
