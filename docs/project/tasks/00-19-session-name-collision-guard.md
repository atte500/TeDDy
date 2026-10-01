# Task: Session Name Collision Guard (Atomic Exclusive Create)

## Business Goal
Prevent silent data corruption of the session audit ledger when two sessions with the same name and timestamp are created concurrently (e.g., multi-agent workflows), including the turn-100 migration path.

## Context
`SessionService.create_session` builds the session root as `.teddy/sessions/{YYYYMMDD_HHMMSS}-{slugified_name}` with second-level timestamp precision and **no uniqueness guard** (`src/teddy_executor/core/services/session_service.py:51-55`). The underlying `IFileSystemManager.create_directory` uses `mkdir(parents=True, exist_ok=True)` (`src/teddy_executor/adapters/outbound/local_file_system_adapter.py:212-217`), so a colliding second writer does NOT fail — it silently overwrites the first session's `session.context`, prompt file, and `01/meta.yaml`.

The user confirmed TeDDy is used for multi-agent workflows, so truly concurrent creation with identical names is a real scenario. An exists-check-then-retry guard is insufficient (TOCTOU race: both processes check, both see nothing, both write). The correct mechanism is **atomic exclusive creation**: `mkdir()` without `exist_ok` raises `FileExistsError` if the directory exists, and this check-and-create is a single atomic OS operation — exactly one process can win. The loser retries with an incremented trailing `-N` suffix, reusing the existing continuation convention from `_calculate_continuation_name` (`session_service.py:494-501`).

**Second collision surface (confirmed by investigation):** the turn-100 migration path has the same bug, and it is worse. `_resolve_next_turn_path` (`session_service.py:486-489`) computes the continuation name with no existence check, and the target is materialized via the same tolerant `mkdir(exist_ok=True)` path (`create_next_turn`, `session_service.py:253-258`). If sessions `...-foo` and `...-foo-2` are both live and both hit turn 99, `...-foo` migrates into `...-foo-2`: it overwrites the sibling's `session.context`, prompt file, and `01/meta.yaml`, then continues creating turns `02`, `03`... interleaved with the sibling's turns — two independent audit ledgers merge into one directory.

**Verified composition:** the regex `-(\d+)$` in `_calculate_continuation_name` handles collision suffixes correctly (`...-foo-2` migrates → `...-foo-3`), so one shared uniqueness mechanism cleanly covers both paths. (Note: a pre-existing quirk where user names ending in `-<digits>` mis-parse — e.g., "fix 404" → `...-fix-405` — is OUT of scope; uniqueness is guaranteed regardless.)

**What deliberately stays the same:** no sub-second timestamps (keeps names readable/sortable); once the session root is atomically claimed, everything under it (including `01/`) is private to the winner, so turn-directory creation stays tolerant.

## Implementation Steps

### Step 1: Add `create_directory_exclusive` to the `IFileSystemManager` port
- **File:** [src/teddy_executor/core/ports/outbound/file_system_manager.py](/src/teddy_executor/core/ports/outbound/file_system_manager.py)
- **Change:** Add method `create_directory_exclusive(self, path: str) -> bool`. Contract: creates the directory (with parents) atomically; returns `True` on success, `False` if the directory already exists (`FileExistsError` caught). Must NOT swallow other errors — re-raise anything that is not `FileExistsError` (Failure Transparency standard).

### Step 2: Update the port's contract documentation
- **File:** [docs/architecture/core/ports/outbound/file_system_manager.md](/docs/architecture/core/ports/outbound/file_system_manager.md)
- **Change:** Document `create_directory_exclusive`, its atomicity guarantee (no check-then-act window; safe for concurrent processes on POSIX and Windows), and its intended use for session-root claiming.

### Step 3: Implement in `LocalFileSystemAdapter`
- **File:** [src/teddy_executor/adapters/outbound/local_file_system_adapter.py](/src/teddy_executor/adapters/outbound/local_file_system_adapter.py)
- **Change:** Implement `create_directory_exclusive`: `self._resolve_path(path).mkdir(parents=True)` inside a `try/except FileExistsError` that returns `False`; return `True` on success. Do NOT pass `exist_ok=True`. Do NOT use a bare/broad except.

### Step 4: Update test-harness fakes for `IFileSystemManager`
- **File:** [tests/harness/setup/mocks.py](/tests/harness/setup/mocks.py) and [tests/harness/setup/mocking.py](/tests/harness/setup/mocking.py)
- **Change:** Add `create_directory_exclusive` to every in-memory fake implementing `IFileSystemManager` (behavior: return `False` if the path is already registered as existing, `True` and register otherwise). Use the designated mock registration helper to prevent signature drift — no bare dynamic mocks.

### Step 5: Add a centralized uniqueness helper in `SessionService`
- **File:** [src/teddy_executor/core/services/session_service.py](/src/teddy_executor/core/services/session_service.py)
- **Change:** Add `_claim_session_root(base_name: str) -> str`: loops building candidate names — starting with `base_name`, then `base_name-2`, `base_name-3`, ... (same trailing-suffix convention as `_calculate_continuation_name`) — and attempts `self._file_system_manager.create_directory_exclusive(f".teddy/sessions/{candidate}")`. On the first `True` return, returns the claimed root path. This is the single shared uniqueness mechanism for both call sites.

### Step 6: Wire the helper into `create_session`
- **File:** [src/teddy_executor/core/services/session_service.py](/src/teddy_executor/core/services/session_service.py)
- **Change:** In `create_session` (lines ~51-57), replace the bare `session_root = f".teddy/sessions/{prefixed_name}"` + `create_turn_directory(turn_dir)` bootstrap with: call `_claim_session_root(f"{timestamp}-{clean_name}")` to atomically claim the root, then derive `turn_dir = f"{session_root}/01"` and create it via the existing tolerant `create_turn_directory` (safe — root is exclusively owned by this process).

### Step 7: Wire the helper into the turn-100 migration path
- **File:** [src/teddy_executor/core/services/session_service.py](/src/teddy_executor/core/services/session_service.py)
- **Change:** In `create_next_turn` (lines ~253-262), when `is_migration` is `True`: exclusive-create `next_session_dir` via the same suffix-retry mechanism BEFORE `_clone_session_artifacts` runs. The candidate base name is the continuation name from `_calculate_continuation_name`; if it is already occupied (e.g., by a sibling live session), increment the suffix and retry. The claimed directory name must be used for `next_dir` and all subsequent persistence (turn dir, meta, context). Non-migration turns are unaffected.

### Step 8: Unit tests — exclusive-create port contract and retry loop
- **File:** [tests/suites/unit/adapters/outbound/test_file_system_adapter_contract.py](/tests/suites/unit/adapters/outbound/test_file_system_adapter_contract.py) and [tests/suites/unit/core/services/test_session_service.py](/tests/suites/unit/core/services/test_session_service.py)
- **Change:** (Red first, per TDD.) Test `create_directory_exclusive`: returns `True` on fresh create, `False` on existing path, creates parent directories, and propagates non-`FileExistsError` errors. Test `_claim_session_root`: claims base name when free; retries with `-2`, `-3` when occupied; stops at first success.

### Step 9: Tests — collision scenarios for both call sites
- **File:** [tests/suites/unit/core/services/test_session_service.py](/tests/suites/unit/core/services/test_session_service.py) and [tests/suites/integration/core/services/test_session_service.py](/tests/suites/integration/core/services/test_session_service.py)
- **Change:** Unit: `create_session` invoked when a session with identical `{timestamp}-{name}` already exists produces a distinct `-2` root and leaves the first session's files untouched. Unit: turn-99 → migration when the continuation session name already exists migrates to `-N+1` instead of writing into the sibling. Integration: simulate a pre-existing sibling session (the concurrent-winner scenario) and assert the sibling's `session.context`, prompt file, and `01/meta.yaml` are byte-identical before/after the second session's creation/migration. All test files must go to OS-designated temp dirs per the Testing Strategy.

## Verification
1. `uv run pytest tests/suites/unit/adapters/outbound/test_file_system_adapter_contract.py -k exclusive` — new port contract tests pass.
2. `uv run pytest tests/suites/unit/core/services/test_session_service.py -k "collision or continuation"` — retry-loop and migration-collision unit tests pass.
3. `uv run pytest tests/suites/integration/core/services/test_session_service.py` — sibling-integrity integration test passes; existing session tests show no regression.
4. Manual check: create a session, then in a second terminal create a session with the same name within the same second — confirm the second gets a `-2` directory and the first's `session.context`, prompt file, and `01/meta.yaml` are unmodified.
5. Manual check: force a session to turn 99 while a sibling `-2` session exists — confirm migration targets `-3` and the sibling's ledger is untouched.
6. Full suite green: `uv run pytest` (post-commit hook enforces this; do not bypass).
