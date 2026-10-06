# Task: resume-by-session-slug

## Business Goal
Allow `teddy resume <slug>` to resolve an existing session from its timestamp-stripped name (e.g. `teddy resume add-user-auth` → `.teddy/sessions/20260124_153000-add-user-auth`), so users no longer have to type or point at the full timestamped folder name.

## Context

### Current behavior
Sessions live at `.teddy/sessions/{YYYYMMDD_HHMMSS}-{slug}`, where `{slug} = slugify(name)` (see `SessionService.create_session` and `SessionRepository.rename_session`; `slugify` lives in `src/teddy_executor/core/utils/string.py`). Both creation AND renaming always prepend the `{YYYYMMDD_HHMMSS}-` prefix, so the human-meaningful part is the suffix.

Today `teddy resume [path]` resolves a session only by **path**:
- `handle_resume_session` → `_resolve_session_name(container, path)` (`src/teddy_executor/adapters/inbound/session_cli_handlers.py`, ~line 906).
- When `[path]` is given, it calls `ISessionManager.resolve_session_from_path(path)`, which (`SessionRepository.resolve_session_from_path`) climbs the directory tree for a directory whose parent is `sessions` and which has `.teddy` in its parts, then falls back to an EXACT `.teddy/sessions/{path}` existence check.
- A bare slug such as `add-user-auth` matches neither and raises `ValueError`.
- When `[path]` is omitted, `_resolve_session_name` tries the CWD and falls back to `get_latest_session_name()`.

The helper `SessionRepository._strip_prefix(name)` — `re.sub(r"^\d{8}_\d{6}-", "", name)` — ALREADY exists for stripping the timestamp prefix, but is currently **UNUSED**. Reuse it (do not re-implement the regex).

### Approved design (user-confirmed in this session)
1. **Overload the existing positional `[path]`; NO new flag.**
2. In `_resolve_session_name`, when `path` is supplied, try `resolve_session_from_path(path)` FIRST; on `ValueError`, fall back to slug resolution.
3. Slug matching is **EXACT and case-insensitive** (`self._strip_prefix(folder).casefold() == slug.strip().casefold()`).
4. Disambiguation is **LATEST-WINS**: when several sessions share the slug, resume the most recently modified one (consistent with `get_latest_session_name`), and surface which one was chosen.

### Constraints / notes
- `resolve_session_from_path` MUST remain the first attempt so ALL existing path-based behavior (CWD-climb, explicit `sessions/` path, exact folder name) is unchanged. Slug resolution is purely additive.
- Continuation folders created by `_claim_session_root` / `_calculate_continuation_name` carry a `-2`, `-3`, … suffix (e.g. `add-user-auth-2`); under EXACT matching a query of `add-user-auth` will NOT match them. This is intended for this task.
- Follow the existing Hexagonal convention used by `resolve_session_from_path`: **port → service → repository**. Do NOT perform filesystem I/O in the CLI adapter.
- This is an ad-hoc (`00-30`) task; it is NOT tracked in a milestone or the PROJECT.md Roadmap.

## Implementation Steps

### Step 1: Declare `resolve_session_from_slug` on the `ISessionRepository` outbound port
- **File:** [src/teddy_executor/core/ports/outbound/session_repository.py](/src/teddy_executor/core/ports/outbound/session_repository.py)
- **Change:** Add the protocol method mirroring `resolve_session_from_path`:
```python
def resolve_session_from_slug(self, slug: str) -> str:
    """Resolves a session folder name from its timestamp-stripped slug."""
    ...
```
If a hand-written `ISessionRepository` double exists under `tests/harness/` or the test suites, update it with a matching stub.

### Step 2: Implement `SessionRepository.resolve_session_from_slug`
- **File:** [src/teddy_executor/core/services/session_repository.py](/src/teddy_executor/core/services/session_repository.py)
- **Change:** Add `import logging` and a module-level `logger = logging.getLogger(__name__)` at the top. Then add the method, reusing `self._strip_prefix(...)` and the mtime-sort pattern from `get_latest_session_name`:
  1. If `.teddy/sessions` does not exist → `raise ValueError("No sessions found.")`.
  2. List `.teddy/sessions/`; for each folder compute `self._strip_prefix(name).casefold()` and keep matches where it equals `slug.strip().casefold()`.
  3. For each match read mtime via `self._file_system_manager.get_mtime(f".teddy/sessions/{name}")`, skipping `FileNotFoundError`/`OSError` (mirror `get_latest_session_name`).
  4. Sort matches by mtime descending and return the newest.
  5. If more than one match, emit an informative `logger.warning(...)` naming the chosen folder.
  6. If no match → `raise ValueError(f"No session found with slug: {slug}")`.

### Step 3: Declare `resolve_session_from_slug` on the `ISessionManager` protocol
- **File:** [src/teddy_executor/core/ports/outbound/session_manager.py](/src/teddy_executor/core/ports/outbound/session_manager.py)
- **Change:** Add the member directly after `resolve_session_from_path`:
```python
def resolve_session_from_slug(self, slug: str) -> str:
    """
    Resolves a session name from its timestamp-stripped slug
    (e.g. 'add-user-auth' -> '20260124_153000-add-user-auth').
    """
    ...
```

### Step 4: Implement `SessionService.resolve_session_from_slug`
- **File:** [src/teddy_executor/core/services/session_service.py](/src/teddy_executor/core/services/session_service.py)
- **Change:** Add the delegate directly after `resolve_session_from_path` (~line 504):
```python
def resolve_session_from_slug(self, slug: str) -> str:
    """Resolves a session name from its timestamp-stripped slug."""
    return self._repository.resolve_session_from_slug(slug)
```

### Step 5: Wire the slug fallback into `_resolve_session_name`
- **File:** [src/teddy_executor/adapters/inbound/session_cli_handlers.py](/src/teddy_executor/adapters/inbound/session_cli_handlers.py)
- **Change:** In `_resolve_session_name` (~line 906), when `path` is supplied, try path resolution first and fall back to slug:
```python
if path:
    try:
        return session_manager.resolve_session_from_path(path)
    except ValueError:
        return session_manager.resolve_session_from_slug(path)
```
Leave the no-`path` branch (CWD-climb → `get_latest_session_name()`) UNCHANGED. Update the docstring to mention the slug fallback. No other change is required — `handle_resume_session` already echoes `Resuming session: .teddy/sessions/<resolved-name>`, which surfaces the chosen folder.

### Step 6: Update the hand-written `ISessionManager` contract double
- **File:** [tests/suites/unit/core/ports/test_session_manager_contract.py](/tests/suites/unit/core/ports/test_session_manager_contract.py)
- **Change:** This file's hand-written `DummyManager` enumerates protocol members by hand, so adding `resolve_session_from_slug` to `ISessionManager` will break its `isinstance(...)` contract check. Add a matching `resolve_session_from_slug` stub to the double (mirror the `resolve_session_from_path` stub).

### Step 7: Unit tests — repository slug resolution
- **File:** [tests/suites/unit/core/services/test_session_repository.py](/tests/suites/unit/core/services/test_session_repository.py)
- **Change:** Add tests:
  1. `test_resolve_session_from_slug_strips_timestamp_prefix` — `add-user-auth` resolves to `20260124_153000-add-user-auth`.
  2. `test_resolve_session_from_slug_is_case_insensitive` — `Add-User-Auth` matches `...-add-user-auth`.
  3. `test_resolve_session_from_slug_latest_wins_on_ambiguity` — two folders sharing the slug → the one with the newer mtime is returned.
  4. `test_resolve_session_from_slug_raises_when_no_match` — expects `ValueError`.
  5. `test_resolve_session_from_slug_raises_when_no_sessions` — expects `ValueError`.

### Step 8: Unit tests — CLI handler fallback
- **File:** [tests/suites/unit/adapters/inbound/test_session_cli_handlers.py](/tests/suites/unit/adapters/inbound/test_session_cli_handlers.py)
- **Change:** Add tests for `_resolve_session_name`:
  1. A `path` that fails `resolve_session_from_path` falls back to `resolve_session_from_slug`.
  2. A `path` that resolves successfully does NOT call `resolve_session_from_slug`.
  3. The no-`path` behavior (CWD-climb → `get_latest_session_name()`) is unchanged.

### Step 9: Acceptance test — end-to-end resume by slug
- **File:** [tests/suites/acceptance/test_session_resume_robustness.py](/tests/suites/acceptance/test_session_resume_robustness.py)
- **Change:** Add an end-to-end test that creates a session (timestamp-prefixed name) and invokes `teddy resume <slug>`, asserting it resumes the correct session.

## Verification
1. `uv run pytest tests/suites/unit/core/services/test_session_repository.py -v` — all green.
2. `uv run pytest tests/suites/unit/adapters/inbound/test_session_cli_handlers.py -v` — all green.
3. `uv run pytest tests/suites/unit/core/ports/test_session_manager_contract.py -v` — contract double satisfies `isinstance`.
4. `uv run pytest tests/suites/acceptance/test_session_resume_robustness.py -v` — all green.
5. Manual: with a session folder `20260124_153000-add-user-auth`, running `teddy resume add-user-auth` prints `Resuming session: .teddy/sessions/20260124_153000-add-user-auth`.
6. Manual: `teddy resume` (no arg) and `teddy resume <valid path>` behave EXACTLY as before (no regression).
7. Manual: `teddy resume nonexistent-slug` fails with a clear `ValueError` ("No session found with slug: nonexistent-slug").
8. `uv run pytest` — full suite green (post-commit gate).
