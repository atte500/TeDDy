# Bug: CI Discrepancy on Latest Commit

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
The latest commit passes all tests locally but fails in the GitHub Actions CI pipeline.

## Context & Scope
### Regressing Delta
- **Commit:** `fc7db1c` ("refactor(core): migrate SessionOrchestrator to async")
- **Commit:** `6141228` ("refactor(session): migrate SessionOrchestrator and SessionPlanner to async")
- **Suspect Changes:** Migration of core orchestration logic from sync to async.

### Environmental Triggers
CI Environment (GitHub Actions).

### Ruled Out
TBD

## Diagnostic Analysis
### Causal Model
1. `test_run_plan_use_case_has_async_counterparts` uses the `container` fixture, which registers real adapters acting on the CWD.
2. `SessionService.create_session` hard-requires `.teddy/init.context`.
3. In CI, `.teddy/init.context` does not exist in the CWD, causing `FileNotFoundError`.
4. Locally, the file exists from previous runs/development, masking the issue.
5. The test lacks proper workspace isolation and initialization.

### Discrepancies
- Pass locally vs Fail in CI. (resolved: Failing test `test_run_plan_use_case_has_async_counterparts` lacked workspace isolation and initialization, making it dependent on a pre-existing `.teddy/init.context` in the CWD, which is present locally but not in CI.)

## Solution
### Implemented Fixes
- Added `container.resolve(IInitUseCase).ensure_initialized()` to `test_run_plan_use_case_has_async_counterparts` to ensure the `.teddy/` workspace is correctly seeded before session creation.

### Prevention
- This ensures the acceptance test is self-contained and reflects the actual application requirement for an initialized workspace.

### Investigation History
- (None)
