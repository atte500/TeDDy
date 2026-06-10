# Slice: Prompt Source Relocation to `.teddy/prompts/`
- **Status:** Completed
- **Type:** Refactor
- **Milestone:** N/A (Ad-hoc)
- **Specs:** [Task: Prompt Source Relocation](/docs/project/tasks/26-prompt-source-relocation.md)
- **Component Docs:** [PromptManager](/docs/architecture/core/services/prompt_manager.md), [InitService](/docs/architecture/core/services/init_service.md), [SessionService](/docs/architecture/core/services/session_service.md)
- **Prototype:** N/A

## Business Goal
Move the canonical source of agent system prompts from bundled Python resources to the user-accessible `.teddy/prompts/` directory, enabling end-user customization and collocating all init templates under `resources/config/prompts/`.

## Scenarios
> As a user, I want to customize agent prompts in `.teddy/prompts/` so that my modifications are reflected in new sessions without editing Python package internals.

```gherkin
Given the project is initialized with `teddy init`
When I edit `.teddy/prompts/pathfinder.xml`
And I start a new session with `teddy start --session -a pathfinder`
Then the session root contains the edited prompt content
And `teddy get-prompt pathfinder` returns the edited content
```

> As a user, I want `teddy init` to restore missing prompts without overwriting my customizations.

```gherkin
Given `.teddy/prompts/` exists with `pathfinder.xml` containing custom content
When I delete `.teddy/prompts/architect.xml`
And I run `teddy init`
Then `.teddy/prompts/architect.xml` is restored from bundled resources
And `.teddy/prompts/pathfinder.xml` still contains my custom content
```

> As a user, I want `fetch_system_prompt` to resolve prompts from `.teddy/prompts/` when no session root override exists.

```gherkin
Given a session is active
And no session-level prompt override exists
When the system fetches the prompt for the `developer` agent
Then it resolves from `.teddy/prompts/developer.xml`
And it does NOT fall back to internal bundled resources
```

## Edge Cases
- **Missing .teddy/prompts/**: If `.teddy/prompts/` is deleted (not just individual files), `teddy init` recreates the directory and restores all 6 prompts.
- **Corrupt prompt file**: If a prompt XML in `.teddy/prompts/` is unreadable, `fetch_system_prompt` logs a warning and returns empty string rather than crashing.
- **Prompt deleted mid-session**: If a prompt is deleted from `.teddy/prompts/` between init and session start, the session init raises a clear `ValueError` suggesting `teddy init`.
- **Legacy session (pre-migration)**: Old sessions retain their prompt snapshot in the session root, so they remain unaffected by this change.
- **Double init**: Running `teddy init` on an already-initialized project checks for prompt existence and only restores missing ones, never overwrites.

## Deliverables
- [x] **Seam** - Relocate bundled prompt files from `resources/prompts/` to `resources/config/prompts/`, delete old directory, update all import references and resource paths across the codebase.
- [x] **Logic** - Add prompt XML copy logic to `InitService` that creates `.teddy/prompts/` and copies the 6 prompt XMLs from bundled resources during `teddy init`, using conditional copy (never overwrite existing).
- [x] **Logic** - Update `SessionService.create_session()` to read prompt content from `.teddy/prompts/<agent>.xml` using `IFileSystemManager` instead of bundled resources.
- [x] **Logic** - Update `PromptManager.fetch_system_prompt()` and `prompts.py:find_prompt_content()` to resolve from session root → `.teddy/prompts/` with no internal resource fallback.
- [x] **Wiring** - Update all test files to reflect new prompt resolution paths and verify cross-cutting behavior via acceptance tests (init → get-prompt → session start flow).

## Implementation Notes
**Seam deliverable (Step 1):**
- Relocated 6 XML prompt files from `resources/prompts/` to `resources/config/prompts/` using `git mv` to preserve history.
- Deleted `resources/prompts/` directory and its `__init__.py`.
- Updated `prompts.py:find_prompt_content()` bundled resource path and docstring to `resources/config/prompts/`.
- No other runtime Python code referenced the old import path (`resources.prompts`), only documentation.
- Created unit test (`test_prompt_resource_relocation.py`) that asserts all 6 bundled prompt XMLs exist at the new location.
- The `resources/__init__.py` had no import for `prompts`, so no change was needed there.
- Full test suite confirmed no regressions.

**Logic deliverable (Step 2):**
- Extended `InitService.ensure_initialized()` to create `.teddy/prompts/` and copy 6 prompt XMLs from bundled `resources/config/prompts/` using conditional copy (only if not existing).
- Followed the same `_get_default_content` pattern used for `.gitignore`, `config.yaml`, and `init.context`.
- Added unit test `test_ensure_initialized_copies_prompts_to_teddy` verifying all 6 prompts are written with correct content.
- Updated existing test `test_ensure_initialized_creates_directory_and_files_if_missing` to expect the additional `create_directory(".teddy/prompts")` call.
- The `test_ensure_initialized_does_not_overwrite_existing_files` test confirmed existing files and directories are never overwritten (path_exists returns True → no writes).
- Full test suite confirmed no regressions.

**Logic deliverable (Step 3):**
- Changed `SessionService.create_session()` to read prompt content from `.teddy/prompts/<agent>.xml` via `IFileSystemManager.read_file()` instead of calling `self._prompt_manager.get_prompt_content()`.
- If the prompt file doesn't exist, raises `ValueError` suggesting `teddy init`.
- Added unit test `test_create_session_reads_prompt_from_teddy_prompts` verifying:
  - Prompt content is written to session root with content from `.teddy/prompts/`
  - `.teddy/prompts/<agent>.xml` is read via filesystem
  - `get_prompt_content` is NOT called (enforced via `side_effect=AssertionError`)
- Updated 4 existing tests (`test_create_session_orchestrates_filesystem_correctly`, `test_create_session_persists_initial_request`, `test_create_session_seeds_initial_request_into_session_context`, `test_create_session_deduplicates_context_paths`) to use `read_file.side_effect` with a dict mapping paths to content, replacing the `get_prompt_content` mock.
- During Integration gate, discovered regression in `test_session_service_pruning.py::test_create_session_does_not_put_prompt_in_turn_directory` — it expected `write_file` with prompt content from `get_prompt_content` mock, but the new code reads from filesystem. Fixed by updating `read_file` setup and removing the `get_prompt_content` mock.
- Full test suite confirmed 891 passed, 3 skipped (no regressions).

**Logic deliverable (Step 4):**
- Changed `PromptManager.fetch_system_prompt()` to replace the internal resource fallback (`resources/prompts/<agent>.xml`) with `.teddy/prompts/<agent>.xml` resolved from project root via `turn_path.parent.parent.parent.parent / ".teddy" / "prompts" / ...`.
- The session-root override (first priority) remains unchanged.
- Changed `prompts.py:find_prompt_content()` to remove the bundled resources fallback entirely. Now only searches `.teddy/prompts/` upward from CWD; returns `None` if not found.
- Added unit test `test_fetch_system_prompt_resolves_from_teddy_prompts` confirming:
  - When session root is missing but `.teddy/prompts/` has the prompt, content is returned from `.teddy/prompts/`.
  - No internal resource fallback exists.
- Added unit test `test_find_prompt_content_does_not_fallback_to_bundled` confirming:
  - When bundled resources exist but `.teddy/prompts/` is empty, returns `None`.
  - No fallback to bundled resources.
- Discovered path calculation bug in initial Green attempt: `parent.parent.parent` (3 levels up from turn path) lands at `.teddy/sessions`, not project root. Fixed to `parent.parent.parent.parent` (4 levels up) to reach project root.
- Full test suite confirmed no regressions.

**Wiring deliverable (Step 5):**
- Fixed `tests/suites/acceptance/helpers.py:setup_project()` to create `.teddy/prompts/` instead of root `prompts/`.
- Fixed `tests/suites/acceptance/test_streamlined_init.py:setup_init_env()` to create `.teddy/prompts/` instead of root `prompts/`.
- Identified that all other test files are already correctly configured:
  - Unit tests (`test_prompt_manager.py`, `test_prompts.py`, `test_session_service.py`, etc.) already updated in Steps 2-4.
  - Integration tests already updated in Turn 33 (`test_session_orchestration_integration.py`).
  - Acceptance tests pass (11 passed) after helper fixes.
  - No remaining references to old `prompts/` path in test files.
- Full test suite confirmed 893 passed, 3 skipped (no regressions).

## Implementation Plan
This slice implements a 5-step relocation of agent prompts from internal Python resources to the user-accessible `.teddy/prompts/` directory.

**Key design decisions:**
1. Bundled prompts stay as init templates under `resources/config/prompts/` (consistent with `config.yaml`, `.gitignore`, `init.context`)
2. `.teddy/prompts/` becomes the single canonical source for runtime resolution
3. Conditional copy ensures user customizations survive re-init
4. Session root prompts remain as audit snapshots (first priority in resolution chain)
5. Resolution order after migration: session root → `.teddy/prompts/` → empty string (no internal fallback)

**Files affected per step:**
- Step 1: Move 6 XMLs, delete `resources/prompts/`, update `prompts.py`
- Step 2: `init_service.py` — add prompt copy logic
- Step 3: `session_service.py` — change prompt source
- Step 4: `prompt_manager.py`, `prompts.py` — change resolution order
- Step 5: Test files — update paths, add new tests
