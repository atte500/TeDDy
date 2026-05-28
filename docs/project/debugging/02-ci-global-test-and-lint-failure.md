# Bug: Global CI Test and Lint Failures
- **Status:** Resolved
- **Milestone:** [N/A]
- **Vertical Slice:** [N/A]
- **Specs:** [N/A]

## Symptoms
1. `test_start_command_short_flags_aliases` fails on Ubuntu, Windows, and macOS in CI.
2. `mypy` reporting signature mismatch in `SessionOrchestrator.resume`.
3. `ruff` reporting 64 violations of banned `MagicMock` and `patch`.

## Context & Scope
### Regressing Delta
Recent changes in `feat(cli): implement start command flags` and `refactor(core): consolidate create_session`.

### Environmental Triggers
- CI environment (GitHub Actions) triggers ANSI-heavy help output for Typer/Rich.

### Ruled Out
- OS-specific logic (fails on all).

## Diagnostic Analysis
### Causal Model
- **Test Failure:** `CliTestAdapter` captures stdout including ANSI codes. The assertion `"--agent" in result.stdout` fails because the raw string contains escape sequences (e.g., `\x1b[1m--agent\x1b[0m`) or the flag is missing from the command definition.
- **Mypy Failure:** `IRunPlanUseCase.resume` signature was updated but the implementation in `SessionOrchestrator` was not aligned, or vice versa.

### Discrepancies
- Local tests pass on macOS. (Resolved: CI environment triggers ANSI-styled Rich output which interferes with simple string matching in tests).

### Investigation History
1. Analyzed CI run 26567371935 logs.
2. Identified `test_start_command_short_flags_aliases` as the sole failing test.
3. Identified Mypy override error in `SessionOrchestrator`.
4. Verified `SessionOrchestrator.resume` is missing the `message` argument and return type required by `IRunPlanUseCase`.
5. Proven via shadow file that stripping ANSI codes in `CliTestAdapter` resolves the help-text matching failure.

## Solution

### Root Cause
1. **ANSI Interference in Tests:** The `CliTestAdapter` used in acceptance tests captured `stdout` exactly as rendered by Typer/Rich. In CI environments, Rich detects terminal capabilities and uses ANSI escape codes for styling. This caused assertions like `"--agent" in result.stdout` to fail because the raw string contained escape sequences (e.g., `\x1b[1m--agent\x1b[0m`) that interfered with plain text matching.
2. **Signature Mismatch:** `SessionOrchestrator.resume` was not updated to match the change in the `IRunPlanUseCase` interface, which added a `message` parameter.

### Proven Fix
1. **ANSI Stripping in Test Harness:** Updated the `CliTestAdapter` to automatically strip ANSI escape sequences from captured `stdout`. This ensures assertions are performed against plain text regardless of environment styling.
2. **Signature Alignment:** Updated `SessionOrchestrator.resume` and `SessionLifecycleManager.resume` to accept the `message: Optional[str]` parameter and properly pass it through the session state machine.

### Systemic Preventative Measures
- **Resilient Test Harness:** Centralize all I/O capturing in the test harness and apply normalization (ANSI stripping) at the source.
- **Contract Enforcement:** Ensure all implementers of `IRunPlanUseCase` adhere strictly to its signature via Mypy.

### Implementation Instructions
1. **Apply to `tests/harness/drivers/cli_adapter.py`:**
   - Add a regex-based `strip_ansi` utility.
   - Use it on `result.stdout` in `run_cli_command` before returning.
2. **Apply to `src/teddy_executor/core/services/session_orchestrator.py`:**
   - Update `resume` signature to include `message: Optional[str] = None`.
   - Pass `message=message` to `self._lifecycle_manager.resume`.
3. **Apply to `src/teddy_executor/core/services/session_lifecycle_manager.py`:**
   - Update `resume` signature to include `message: Optional[str] = None`.
   - Ensure the parameter is passed to planning and execution handlers.
