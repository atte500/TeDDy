# Bug: Chunked Dispatch Exposed a Wiped termios Patch Target on macOS
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
The macOS CI job reported one failure on the first push that enabled chunked dispatch. `test_console_ask_loop_stdin_flush.py::test_flush_stdin_called_when_in_tty_mode` asserted that `termios.tcflush` was called once and observed zero calls. The same suite is green in every local Windows run, and the failure is reported only from the macOS job.

Minimal reproduction: the MRE installs a synthetic terminal module, wipes it, and then replaces it through `patch.dict`. The subject re-imports the module at call time, so the spy on the original object records zero calls. The same script repeats the pattern with `monkeypatch.setitem` and records exactly one call.

## Context & Scope
### Regressing Delta
Commit f046b6f0 added `--dist worksteal` to the `addopts` list in `pyproject.toml`. The flag does not change test code. It changes which tests share one worker process, which exposed a latent global-state wipe in `tests/suites/unit/adapters/outbound/test_tty_guards.py`.

### Environmental Triggers
A POSIX host with the real `termios` module, plus one worker process that runs `test_tty_guards.py` before `test_console_ask_loop_stdin_flush.py`. Windows cannot trigger the failure, because the victim class is skipped when `termios` is absent.

### Ruled Out
- The production restore sites: `_flush_stdin`, `restore_cooked_mode`, and `SystemEnvironmentAdapter.run_command` all import `termios` inside the function and behave correctly.
- The `tcflush` call itself: it never ran, because the call-time import resolved a different module object.
- A second leaking site: every other test replaces the entry through `monkeypatch.setitem`, which restores the bound object.

## Diagnostic Analysis
### Causal Model
1. `test_console_ask_loop_stdin_flush.py` binds the real `termios` module at import time, and its test spies on `termios.tcflush`.
2. `ConsoleAskLoop._flush_stdin` resolves `termios` through a function-local import at call time.
3. The `mock_termios` fixture deleted `sys.modules["termios"]` and then entered `patch.dict("sys.modules", {"termios": fake})`. `patch.dict` snapshots the mapping after the delete, so its teardown restored a mapping without `termios`.
4. Every later call-time import in that worker built a fresh module object. The spy stayed bound to the original object, so it recorded zero calls.
5. The two `importlib.reload` calls inside the block could not help, because neither reloaded module holds a module-scope `termios` binding.

### Discrepancies
- [x] macOS reports `tcflush` called 0 times. (Resolved: the fixture left `sys.modules` without `termios`, so the call-time import built a fresh object.)
- [x] Windows and the local suite stay green. (Resolved: the victim class is skipped without `termios`, so the wipe has no observable victim on Windows.)
- [x] `patch.dict` did not restore the real module. (Resolved: the delete ran before the snapshot.)
- [x] The module reloads did not reach the production call sites. (Resolved: all three sites import `termios` inside the function.)
- [x] No second test leaks the entry. (Resolved: the search listed `test_tty_guards.py` as the only delete-then-`patch.dict` site.)

### Investigation History
1. Reviewed the failing macOS job log; the only failing assertion is `tcflush` called 0 times in the stdin-flush test.
2. Searched every `sys.modules` mutation under `tests/`; `test_tty_guards.py` is the only site that deletes the entry before `patch.dict`, and every other site uses `monkeypatch.setitem`.
3. Built `01-sys-modules-wipe-mre.py`; the wipe left the entry absent and the spy at zero calls, and `monkeypatch.setitem` restored the bound object with exactly one call.
4. Read `console_interactor_ask_loop.py`, `console_interactor_helpers.py`, and `system_environment_adapter.py`; all three import `termios` inside the function, so no module reload is required.
5. Replaced the fixture with a `monkeypatch.setitem` install and removed the dead `importlib` import and the two reloads.
6. Ran the six terminal-related test modules in one process; 26 passed and 5 skipped.
7. Ran the full suite; 1,839 passed and 36 skipped in 23.81s.
8. Staged the file with the commit and ran the hook's linter; `TID251` flagged the bare `unittest.mock.patch` and `MagicMock` imports, so the fixture was rebuilt as a hand-built `SimpleNamespace` fake and the context-manager patches were replaced with `monkeypatch` setters. This also clears one of the five pre-existing `TID251` modules tracked for Milestone 5.

9. Ran the hook's linter on the rewritten file and observed "All checks passed!"; ran the six terminal modules in one process, then the full suite, and observed 26 passed and 5 skipped, then 1,839 passed and 36 skipped in 23.07s.

### Reproduction Artifacts
- [Minimal reproducible example](/spikes/debug/worksteal-macos-leak/01-sys-modules-wipe-mre.py)

## Solution
### Root Cause
The `mock_termios` fixture wiped the real `termios` entry before `patch.dict` took its snapshot. Teardown then restored a mapping without `termios`, so every later call-time import in that worker built a fresh module. The stdin-flush test spied on the original module object and therefore observed zero calls. Chunked dispatch made a late-ordered guard module run before an early-ordered victim module inside one worker, which turned the latent wipe into a failure. The fix was proven by the MRE and applied directly to the test file.

### Affected Components
- `test_tty_guards.py`: the fixture installs a hand-built `SimpleNamespace` termios fake through `monkeypatch.setitem`, which restores the real module on teardown. The dead `importlib` import, the two reloads, and the banned `unittest.mock.patch`/`MagicMock` imports are removed; the stream predicates and the shell-out now use `monkeypatch` setters.
- `test_console_ask_loop_stdin_flush.py`: unchanged; its module-scope binding and spy now resolve the same module again.
- `pyproject.toml`: unchanged; the dispatch flag stays as shipped.
- Production adapters: unchanged; every restore site already imports `termios` inside the function.
