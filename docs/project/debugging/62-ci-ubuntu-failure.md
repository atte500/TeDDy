# Bug: ci-ubuntu-failure
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
**Expected:** The `ci.yml` `Test Suite` matrix passes on all three legs (ubuntu-latest, macos-latest, windows-latest).

**Actual:** User reports the **ubuntu-latest** leg is now failing ("now ubuntu failed it seems"). Recent `ci.yml` runs on `main` show a persistent series of `failure` conclusions around the concurrent `feat(editor)` (Slice 03-01) commits — e.g. `1a5aa995`, `d34144f9`, `f5ebaa5e`, `35176d2a`, `e4e80485`, `b12542da`, `56a93294`, `c9d2b8a1`, `1287e91d`. The Bug-61 `os.killpg` fix is already on `main` (commit `a4d0f058`), so this is a distinct failure mode.

**Minimal reproduction steps (observed via CI logs, run `37114257569` / sha `1a5aa995`):** `Test Suite (ubuntu-latest)` fails the `Run Tests` step (`uv run pytest`) with a SINGLE pyfakefs fixture SETUP error:

```
____ ERROR at setup of test_list_directory_recursive_dot_resolves_correctly ____
.venv/lib/python3.14/site-packages/pyfakefs/fake_os.py:1488: in wrapped
    return getattr(os, f.__name__)(*args, **kwargs)
E  AttributeError: module 'os' has no attribute 'dir'
ERROR tests/suites/unit/adapters/outbound/test_file_system_adapter_recursion.py::test_list_directory_recursive_dot_resolves_correctly
================== 1514 passed, 8 skipped, 1 error in 32.06s ===================
```

The error originates inside pyfakefs's `Patcher.__init__` → `_init_fake_module_functions` (`fake_filesystem_unittest.py:761/847`) while it evaluates `fake_module.dir()` — i.e. during fake-module construction, **before** the SUT (`LocalFileSystemAdapter`) runs. The `macos-latest` and `windows-latest` legs passed in the same run.

## Context & Scope
### Regressing Delta
No single TeDDy commit introduced the defect: the root cause is a latent, pre-existing class-attribute leak inside the third-party `pyfakefs` dependency (not our code). The ubuntu-latest failure surfaced during the concurrent `feat(editor)` Slice 03-01 commit series (e.g. run `37114257569` / sha `1a5aa995`), whose added test files shifted the pytest-xdist work distribution so that an `fs`-fixture test landed, on some worker, after the (unidentified) test that left `FakeOsModule.use_original` True. The Bug-61 windows fix (`a4d0f058`) is a Linux no-op and is unrelated.

### Environmental Triggers
- OS: ubuntu-latest (per user report).
- Runtime: Python 3.14.

### Ruled Out
- Bug-61 `os.killpg` windows-only test-seam defect (fixed in `a4d0f058`; that change is a no-op on Linux, so it cannot cause an ubuntu failure).

## Diagnostic Analysis
### Causal Model
pyfakefs's `fs` pytest fixture constructs a `Patcher()`. `Patcher.__init__` calls `_init_fake_module_functions()`, which iterates the fake module CLASSES and, for each, calls the class-level `fake_module.dir()` to enumerate the faked function names. `FakeOsModule` owns a `dir` method wrapped by `handle_original_call`. That wrapper computes `should_use_original = FakeOsModule.use_original`; when True it executes `getattr(os, f.__name__)` — i.e. `getattr(os, "dir")`. The real `os` module has no `dir` attribute, so this raises `AttributeError: module 'os' has no attribute 'dir'`, aborting the `fs`-fixture SETUP before any SUT code runs.

`FakeOsModule.use_original` is a CLASS attribute (global, per process / per xdist worker); its default is False. Because the class-level `dir()` call passes NO arguments, the wrapper's instance/`skip_names` delegation branch (`if not should_use_original and args`) is unreachable here — the flag MUST be True for the crash. The mechanism was reproduced locally by forcing the flag True (Turn 29: exact CI traceback). The TRIGGER that leaves the flag True on CI is not locally reproducible: pyfakefs's `use_original_os()` context manager is the SOLE setter (setter `fake_os.py:1506`, `finally` resetter `:1509`), TeDDy's repo has ZERO references to `use_original`/`Patcher` (it consumes only the `fs` fixture), and a full-suite leak-watch plugin recorded ZERO leak events locally (`1518 passed, 5 skipped`, Turn 30). The local venv is Python 3.13 while CI runs Python 3.14, and the trigger is order/xdist-distribution dependent. The defensive harness poka-yoke (autouse reset of `FakeOsModule.use_original` around every test) was PROVEN to neutralize the crash: a two-test repro (test A leaks the flag; test B requests `fs`) errored at test B's SETUP with the exact CI `AttributeError` when unguarded, and both passed with the reset fixture active (Turn 31).

### Discrepancies
- The Bug-61 fix targeted the windows-latest leg only, yet the ubuntu-latest leg is now reported failing. Conflict: a fix scoped to the Windows-only `os.killpg` symbol should not introduce an ubuntu failure. (Partially resolved: the Bug-61 change is a no-op on Linux — it only added a `sys.platform == "win32"` skip — and the failing run `37114257569` is a concurrent `feat(editor)` commit that merely descends from the fix. The ubuntu failure is a distinct, pyfakefs-internal defect.)
- The failing test errors in fixture SETUP inside pyfakefs, before the SUT runs; yet it passed in the macos/windows legs of the same run. Conflict: a deterministic pyfakefs/Python-3.14 incompatibility should fail on every leg. (resolved: the defect is NOT deterministic — it depends on a leaked global `FakeOsModule.use_original=True` on one xdist worker, so it surfaces only when the worker's distribution happens to place an `fs`-fixture test after the leaking test; that is why the macos/windows legs of the same run passed.)
- The failure did NOT reproduce locally (Turn 28): the test passed in isolation (`1 passed`) and the whole module passed under pytest-xdist (`3 passed`). Conflict: if the defect were deterministic it should reproduce locally. (resolved: the leak is per-process global state and ordering-dependent; a single isolation run or the module alone does not recreate the triggering order. The MECHANISM was reproduced by forcing the flag True — Turn 29 — but the TRIGGER order is not reproduced locally; confirmed Turn 30 — a full-suite watch plugin recorded ZERO leak events across `1518 passed, 5 skipped`, and pyfakefs's own source shows `use_original_os()` is the sole setter (with a `finally` reset) while the repo has no `use_original` reference at all. The trigger is therefore not locally reachable (local venv Python 3.13 vs CI Python 3.14) and is order/distribution-dependent on CI. Fix direction: a trigger-agnostic defensive harness poka-yoke that resets `FakeOsModule.use_original` around every test — PROVEN in Turn 31: the two-test repro errored at test B's `fs` SETUP under the leaked flag and passed 2/2 with the reset fixture active, without touching `src/` or `tests/`.)

### Investigation History
1. Hypothesis: the reported ubuntu failure is a distinct, newly-surfaced CI failure on `main`. Observation: newest completed `failure` run is `37114257569` (sha `1a5aa995`, a `feat(editor)` commit); its matrix is `macos-latest` success, `windows-latest` success, `ubuntu-latest` failure, `Quality Checks` failure (non-blocking). Conclusion: the ubuntu `Test Suite` leg genuinely fails; the windows leg (Bug-61's target) is now green.
2. Hypothesis: the ubuntu failure is a real test failure in the SUT. Observation: the failure is a pyfakefs `fs`-fixture SETUP error (`AttributeError: module 'os' has no attribute 'dir'` at pyfakefs `fake_os.py:1488`), raised inside `Patcher.__init__` before any SUT code runs; it is the only failure (`1514 passed, 8 skipped, 1 error`). Conclusion: the defect is inside pyfakefs's fake-module construction, not the adapter under test.
3. Hypothesis: the defect is deterministically reproducible locally. Observation (Turn 28): `git grep` found NO code injecting a `dir` attribute into `os`; the failing test passed in isolation and the whole module passed under `-n 4` xdist. Conclusion: NOT reproduced locally → order/distribution-dependent (consistent with the PROJECT.md order-dependent-flake precedent for this file). Next: inspect pyfakefs internals (`_init_fake_module_functions`, `FakeOsModule.use_original`) and probe the `os.dir` lookup mechanism.
4. Hypothesis: the crash requires pyfakefs's global `FakeOsModule.use_original` flag to be True when a `Patcher()` is constructed. Observation (Turn 29, local probe): default `use_original=False` → `[default] Patcher() OK`; after setting `FakeOsModule.use_original=True` → `[forced use_original=True] Patcher() RAISED: AttributeError: module 'os' has no attribute 'dir'` with a traceback identical to CI (`fake_filesystem_unittest.py:761` → `:847 for fct_name in fake_module.dir()` → `fake_os.py:1488 getattr(os, f.__name__)`). Reading the pyfakefs source confirmed `_init_fake_module_functions` calls the CLASS-level `FakeOsModule.dir()` (no args), so the instance/`skip_names` branch is unreachable and the flag must be True. Conclusion: mechanism CONFIRMED — a leaked/leftover `use_original=True` (a global class attribute, hence per-xdist-worker) makes the next `fs`-fixture `Patcher()` construction crash. Remaining unknown: what sets the flag True in the full suite.
5. Hypothesis: the leak is reproducible under the full suite with a per-test watch plugin, naming the leaking test. Observation (Turn 30): pyfakefs's own source census confirmed `use_original_os()` is the SOLE setter of `FakeOsModule.use_original` (setter `fake_os.py:1506`, `finally` resetter `:1509`); the repo census found ZERO TeDDy references (`git grep use_original -- src tests .githooks` → none); and `PYTHONPATH=spikes/debug uv run pytest -p spike_use_original_watch -q` closed at `1518 passed, 5 skipped in 8.66s` with the watch log EMPTY/absent — no test ever left the flag True. Conclusion: the trigger is NOT locally reproducible. Two environmental facts explain it — the local venv is Python 3.13 whereas CI runs Python 3.14 (the CI traceback cites `.venv/lib/python3.14/.../fake_os.py:1488`), and the leak is order/xdist-distribution dependent. With no reachable trigger and no TeDDy setter, the fix must be a trigger-agnostic defensive harness poka-yoke (reset the flag around every test), matching the project's existing autouse harness guards (`reset_formatter_singleton`, `clean_test_env`, `guard_os_killpg`). Zero-Touch proof planned via a two-test leak→crash repro toggled by a mirrored spike conftest.
6. Hypothesis: an autouse harness poka-yoke that resets `FakeOsModule.use_original` around every test neutralizes the leak regardless of its origin. Observation (Turn 31, Zero-Touch proof; `src/` and `tests/` untouched): the two-test repro `spikes/debug/test_use_original_leak_repro.py` (test A sets the flag True; test B requests the `fs` fixture) run serially with the guard OFF produced `1 passed, 1 error` — the error at test B's SETUP being the byte-faithful CI `AttributeError: module 'os' has no attribute 'dir'` (`run1 exit=1`); the identical run with the guard ON (`TEDDY_POKA_YOKE=1`, mirrored in `spikes/debug/conftest.py`) produced `2 passed` (`run2 exit=0`). Conclusion: the autouse reset fixture deterministically neutralizes the leak. Root cause and fix are empirically proven without touching production or test code; ready for the Alignment gate.
7. Hypothesis (Systemic Audit): the leak is an instance of a general "unreset third-party global state" class, and pyfakefs exposes no other relevant toggle. Observation (Turn 34 census): `pyproject.toml` sets `testpaths = ["tests"]` and `norecursedirs = "spikes"` (so the deliberately-leaking MRE is never collected by CI); the project already ships autouse harness guards (`reset_formatter_singleton`, `clean_test_env`, `guard_os_killpg`) establishing the idiom; the only class-level mutable flags in pyfakefs are `FakeOsModule.use_original` (the culprit) and `TestCase.PATCH_DEFAULT_ARGS` (unrelated to the pytest `fs` fixture); `use_original_os()` is called only by pyfakefs internals (`fake_filesystem_unittest.py:151/158`, `fake_pathlib.py:1158`); and the adjacent order-dependent flake is already logged as PROJECT.md debt. Conclusion: the single autouse reset fixture covers the whole class; no other instances exist, so no further `[DEBT]` deliverable is required (the fix is trivial → PROJECT.md logging skipped per the workflow).

## Solution

**Root cause (third-party global-state leak; not a TeDDy defect).** pyfakefs's `fs` pytest fixture constructs a `Patcher()`. During construction, `_init_fake_module_functions()` calls the CLASS-level `FakeOsModule.dir()` with no arguments, whose `handle_original_call` wrapper computes `should_use_original = FakeOsModule.use_original`. When that CLASS attribute is `True`, the wrapper executes `getattr(os, "dir")` — the real `os` module has no `dir`, so it raises `AttributeError: module 'os' has no attribute 'dir'` and aborts the `fs`-fixture SETUP before any SUT code runs.

`FakeOsModule.use_original` is a process-global class attribute (pyfakefs toggles it via its own `use_original_os()` context manager, which resets it in a `finally`). Under pytest-xdist, a leftover `True` on one worker poisons whichever later `fs`-fixture test that worker happens to run — hence the order/distribution-dependent, single-test ubuntu failure while the macos/windows legs of the same run pass. The SUT (`LocalFileSystemAdapter`) never executes; the crash is in fixture SETUP.

The exact trigger that leaves the flag `True` on CI was not locally reproducible (local venv Python 3.13 vs CI Python 3.14; pyfakefs's source shows `use_original_os()` is the sole setter, with a `finally` reset; TeDDy's repo has zero `use_original`/`Patcher` references).

**Fix (harness-only, trigger-agnostic).** Add an autouse fixture to `tests/conftest.py` that resets `FakeOsModule.use_original` around every test:

```python
@pytest.fixture(autouse=True)
def reset_pyfakefs_use_original():
    """Poka-Yoke: neutralize a leaked pyfakefs global flag between tests."""
    import pyfakefs.fake_os as fake_os
    fake_os.FakeOsModule.use_original = False
    yield
    fake_os.FakeOsModule.use_original = False
```

It clears the flag both before (a leak from a previous test) and after (a leak within the current test) every test, so it deterministically neutralizes the leak regardless of its origin — no need to identify the exact CI setter first. Test-harness-only (zero production impact), and it matches the project's existing autouse-guard idiom (`reset_formatter_singleton`, `clean_test_env`, `guard_os_killpg`).

**Evidence (Zero-Touch Verification — `src/` and `tests/` untouched).**
- Mechanism probe (Turn 29): forcing `FakeOsModule.use_original = True` reproduced the byte-identical CI traceback (`fake_filesystem_unittest.py:761` -> `:847` -> `fake_os.py:1488`).
- Two-test repro `spikes/debug/test_use_original_leak_repro.py` (Turn 31): guard OFF -> `1 passed, 1 error` with the exact CI `AttributeError` at test B's `fs` SETUP (`exit=1`); guard ON (`spikes/debug/conftest.py`, `TEDDY_POKA_YOKE=1`) -> `2 passed` (`exit=0`).

**Preventative measures (systemic).** The defect class is "an unreset third-party global/class attribute contaminates a later test". Prevention:
1. Keep the autouse reset fixture and add a harness regression test proving a leaked `use_original` no longer crashes a subsequent `fs`-fixture test.
2. Prefer the established autouse harness-guard idiom (explicit state reset at test boundaries) over per-test workarounds for any third-party global state.
3. Rejected alternative: pinning/downgrading `pyfakefs` in `uv.lock` — it masks the symptom on one Python version and re-introduces the fragility at the next bump.
