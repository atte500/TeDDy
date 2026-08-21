# Bug: Pre-commit check not logged when `which` fails silently

- **Status:** Resolved
- **Milestone:** [N/A]
- **Vertical Slice:** [N/A]
- **Specs:** [N/A]

## Symptoms

**Expected:** In every project, TeDDy verifies that Git and pre-commit hooks are initialized and **logs** the result of the pre-commit availability check (e.g., during startup/init).

**Actual:** In some projects, the pre-commit check is not logged at all. Reported hypothesis: on some systems the `which` command is not configured (not on PATH, or no `which` binary) and the check fails silently, so no log entry is produced.

**Minimal reproduction steps:**
1. Ensure `.pre-commit-config.yaml` exists and `pre-commit` resolves via `shutil.which`.
2. Make the `pre-commit install` subprocess fail (e.g., `core.hooksPath` set, unwritable `.git/hooks`).
3. Run `teddy start` — no yellow warning is shown for the failed install; only a debug-level log entry is produced (invisible at default logging config).
4. Similarly, `shutil.which` raising `PermissionError` (unreadable PATH entry) propagates to the outer handler, producing a generic `Error: {e}` instead of a yellow warning.

## Context & Scope

### Regressing Delta
The pre-commit health check was implemented as part of Task 00-05 (Pre-commit Install to Start). The implementation lives in:
- `src/teddy_executor/adapters/inbound/session_cli_handlers.py` — functions `_ensure_commit_hooks()` and `_check_git_initialized()`.
Both functions use `shutil.which()` (Python standard library) to locate tools, NOT the shell `which` command.
The fallback paths:
1. When `shutil.which` returns None → yellow warning via `typer.secho`.
2. When the subprocess (`pre-commit install` or `git init`) fails → `logger.debug` only (no console output).

These functions are present in the current workspace HEAD. The local branch is 26 commits behind origin/main (the local regression exists independent of upstream state).

### Environmental Triggers
- Systems where `pre-commit` CLI is not installed (shutil.which returns None) → Yellow warning should be displayed. If not, something is wrong.
- Systems where `pre-commit` is installed but the `install` command fails (e.g., permissions, missing config) → Only `logger.debug` is called, resulting in **complete silence** (no console output). This may be the source of "not logged".
- The bug title mentions "which is not configured and fails silently" — but the code does NOT call the shell `which` command. This is a discrepancy.

### Ruled Out
- `.githooks/post-commit` uses `command -v poetry` (shell built-in), not `which`.
- The shell `which` command is not used anywhere in the health check code path.

## Diagnostic Analysis

### Causal Model
The pre-commit and git health checks (`_ensure_commit_hooks()`, `_check_git_initialized()`) in `session_cli_handlers.py` use `shutil.which` (Python stdlib), NOT the shell `which` command. Verified behavior:

1. **Tool/config absent** (`shutil.which` returns None, or `.pre-commit-config.yaml` missing) → yellow `typer.secho` warning IS emitted (verified by MRE step 2).
2. **Tool present, subprocess fails** (`subprocess.CalledProcessError`) → only `logger.debug(exc_info=True)` is invoked; zero console output. This is the **silent path** explaining "precommit check not logged". Real-world triggers include `pre-commit install` failing (e.g., `core.hooksPath` set, hook env creation failing, read-only `.git/hooks`) or `git init` failing.
3. **`shutil.which` itself raises** (e.g., `PermissionError`) → no guard around the call; the exception propagates to the handler's outer `try/except Exception`, producing a generic `Error: {e}` instead of the expected yellow warning.

The user's "which is not configured and fails silently" hypothesis is partially misattributed: the code never shells out to `which`; the configured-but-failing branch is silent because Task 00-05 explicitly says to "log a debug message and return (do not show any notification)".

### Discrepancies
- The bug title references the shell `which` command, but the code uses `shutil.which` and never invokes the `which` binary. (Resolved: `git grep` step 1 confirmed no shell `which` call in the health-check path.)
- Hypothesis "which returns None → silent" contradicts observed code: the None branch emits a yellow warning. (Resolved: MRE step 2 confirmed the warning; the silent path is the subprocess-failure branch, confirmed by probe step 3.)

### Investigation History
1. `git grep` located the health checks in `session_cli_handlers.py`; they use `shutil.which` (Python stdlib), not the shell `which` command. Task 00-05 spec confirms the intended branch behaviors.
2. MRE (`spikes/debug/16-precommit-mre.py`) with `shutil.which` returning None confirmed the yellow warning IS emitted. The "which not found → silent" hypothesis is disproven for the None/absent branches.
3. Probe (`spikes/debug/16-precommit-mre_silent_paths.py`): CONFIRMED — when `subprocess.run` raises `CalledProcessError` (`pre-commit install` / `git init`), zero `typer.secho` calls occur; only `logger.debug` runs. This is the console-silent "not logged" path.
4. Probe: CONFIRMED — when `shutil.which` raises (`PermissionError`), the exception propagates uncaught; the outer `try/except Exception` in `handle_new_session`/`handle_resume_session` would print a generic `Error: ...` rather than the expected yellow warning.

## Solution

### Root Cause

The startup health checks (`_ensure_commit_hooks()` and `_check_git_initialized()`) in `session_cli_handlers.py` have two silent failure paths:

1. **Subprocess failure (primary "not logged" path):** When the tool is found and the subprocess runs but fails (e.g., `pre-commit install` fails due to permissions or `core.hooksPath` settings), the exception is caught and only `logger.debug(exc_info=True)` runs. No console output is produced, even though the feature is described as "non-blocking advisory." This was intentional per Task 00-05 spec step 6 ("do not show any notification").

2. **Unguarded `shutil.which` calls:** If `shutil.which` itself raises (e.g., `PermissionError` from an unreadable PATH entry in restricted environments), the exception percolates to the outer handler, producing a generic `Error: {e}` rather than the expected yellow warning.

The user's initial hypothesis — that the shell `which` command is unavailable — is partially misattributed: the code never shells out to `which`; it uses Python's `shutil.which`. The real "not logged" path is the subprocess-failure branch.

### Proven Fix (Shadow File Verification)

A delta shadow file `spikes/debug/shadow_session_cli_handlers.py` redefines only the two faulty functions; all other symbols are re-exported from the unmodified production module. The fix:

1. **Subprocess failure now emits a yellow warning.** Both `except subprocess.CalledProcessError` blocks call `typer.secho("⚠ pre-commit install failed" / "⚠ git init failed", fg=typer.colors.YELLOW, err=True)` before returning, while keeping `logger.debug(exc_info=True)` for the diagnostic trace.

2. **`shutil.which` lookups are guarded.** Both calls are wrapped in `try/except (OSError, AttributeError)` (covers `PermissionError`, the most common PATH-access failure). On failure, a yellow warning (`⚠ Could not check for pre-commit CLI` / `⚠ Could not check for git CLI`) is emitted and the error is logged at debug level.

Zero-touch verification script `spikes/debug/16-precommit-shadow_verify.py` runs `poetry run python spikes/debug/16-precommit-shadow_verify.py` and compares the real (buggy) module against the shadow (fixed) module:

| Scenario | Real module (buggy) | Shadow module (fixed) | Result |
| --- | --- | --- | --- |
| 1. `pre-commit install` fails | 0 secho calls (SILENT) | 1 yellow warning | ✅ |
| 2. `git init` fails | 0 secho calls (SILENT) | 1 yellow warning | ✅ |
| 3. `shutil.which` raises `PermissionError` | exception propagates | 1 yellow warning, no exception | ✅ |
| 4. `shutil.which` returns None (regression) | yellow "not found" warning | yellow "not found" warning (unchanged) | ✅ |
| 5. install succeeds (regression) | green success | green success (unchanged) | ✅ |

The fix has NOT yet been applied to `src/`; that is the pending Implementation phase (write regression test → RED, apply fix, run full suite).

### Preventative Measures

To prevent this entire class of issue globally:

**Mandate compound handling for health-check subprocesses:** All advisory health-check functions that run subprocesses MUST:
- Show a yellow warning on failure (consistent with the "non-blocking advisory" design).
- Always call `logger.debug(exc_info=True)` for the diagnostic trace.
- Never leave the console silent on failure.

**Gate: Categorize and audit all `except` blocks that swallow errors.** This bug is a concrete instance of the "Failure Transparency" debt already logged in PROJECT.md. A dedicated slice should audit the codebase for:
- Bare `except` blocks without logging or re-raise.
- Subprocess calls with `capture_output=True` that can fail silently.
- Unguarded `shutil.which` calls that can propagate exceptions (`shell_command_builder.py` lines 79/87, `system_environment_adapter.py` line 11 — outside the scope of this bug but flagged for review).

### Verification

- Baseline MRE `spikes/debug/16-precommit-mre_silent_paths.py` confirmed the original silent behavior.
- Zero-touch shadow verification `spikes/debug/16-precommit-shadow_verify.py` confirmed the fixed behavior without modifying `src/` or `tests/`.
- Pending Implementation phase: add a regression test to `tests/suites/unit/adapters/inbound/test_session_cli_handlers.py`, apply the two-function fix to `session_cli_handlers.py`, and run the full test suite.
