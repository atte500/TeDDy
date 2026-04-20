# Bug: Session Path Resolution Failure due to Natural Name stripping

- **Status:** Resolved
- **Milestone:** Milestone 10

## Symptoms
Session management commands (`start`, `resume`) fail with "Session not found" errors (CLI exit code 1) because the repository strips date prefixes before passing session names to services, but services use these names to build filesystem paths.

## Context & Scope
### Regressing Delta
The introduction of `YYYYMMDD_HHMMSS-` prefixing in `SessionService.create_session` and the subsequent stripping of this prefix in `SessionRepository` (Commit `5eca65d0884179b36bd298dd701db4d97188827d`).

### Environmental Triggers
Any session operation involving existing sessions (e.g., resuming a session or continuing a session after the first turn in `start`).

## Diagnostic Analysis
### Causal Model
1. `SessionService.create_session` creates a folder with a timestamp prefix (e.g., `20260420_180000-my-feat`).
2. `SessionRepository.resolve_session_from_path` and `get_latest_session_name` return the "Natural Name" (stripped of prefix, e.g., `my-feat`).
3. CLI handlers use this Natural Name to call `SessionOrchestrator.resume`.
4. `SessionOrchestrator` calls `SessionService.get_session_state(session_name)`.
5. `SessionService` attempts to access `.teddy/sessions/{session_name}`, which does not exist because it lacks the prefix.

### Discrepancies
- `SessionRepository.resolve_session_from_path` returns stripped name, but services need folder name for I/O. (resolved: Services will now receive the full folder name)
- `SessionRepository.get_latest_session_name` returns stripped name, breaking `resume` (auto-detect). (resolved: Will return folder name)

### Investigation History
- **2026-04-20:** Identified mismatch between Natural Name and Folder Name as the root cause of CLI exit 1 in session tests.
- **2026-04-20:** Implemented fix: Repository now returns folder names; CLI handlers handle display-only stripping. Verified via acceptance and unit tests.

## Solution
### Implemented Fixes
- Modified `SessionRepository.resolve_session_from_path` and `get_latest_session_name` to return the full folder name (preserving date prefixes).
- Updated `handle_resume_session` in `session_cli_handlers.py` to strip prefixes only when echoing the session name to the user.
- Updated `tests/suites/unit/core/services/test_session_repository.py` to assert full folder names.

### Prevention
The fix is guarded by the regression tests in `test_session_resume_robustness.py`, which verify path resolution from session roots, turn directories, and specific files within turns.
