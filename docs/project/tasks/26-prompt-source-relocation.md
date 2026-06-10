# Task: Prompt Source Relocation to `.teddy/prompts/`

## Business Goal
Move the canonical source of agent system prompts from bundled Python resources to the user-accessible `.teddy/prompts/` directory, eliminating the internal resource fallback and enabling end-user customization.

## Context

Agent prompts (6 XML files: `pathfinder`, `architect`, `developer`, `debugger`, `assistant`, `prototyper`) currently live in two locations:

1. **Bundled source:** `src/teddy_executor/resources/prompts/` — used as the authoritative source during `teddy get-prompt` and copied to session roots.
2. **Session root:** `<session>/<agent>.xml` — an audit copy created during session initialization, prioritized first by `PromptManager.fetch_system_prompt`.

The problem: Bundled resources are inside the Python package and not editable by end users. Even if a user edits prompts in `.teddy/prompts/` (which `get-prompt` checks via config but doesn't use as canonical), those edits have zero effect on sessions because sessions source prompts from bundled resources.

**Solution:** Make `.teddy/prompts/` the single canonical source. The flow becomes:

- `teddy init` copies the 6 prompt XMLs from bundled resources to `.teddy/prompts/` (user-editable)
- Session initialization copies prompts from `.teddy/prompts/` (not internal resources)
- `PromptManager.fetch_system_prompt` resolves: session root → `.teddy/prompts/` (no internal fallback)
- `find_prompt_content` (for `teddy get-prompt`) resolves from `.teddy/prompts/` (no internal fallback)
- Bundled resources are only used as init templates, consistent with how `config.yaml`, `.gitignore`, and `init.context` are handled

Additionally, the bundled prompts are moved from `resources/prompts/` to `resources/config/prompts/` to collocate all init templates in one logical tree.

**Resolution priority after change:**
1. Session root (`<session>/<agent>.xml`) — audit copy (kept as-is)
2. `.teddy/prompts/<agent>.xml` — new canonical source (user edits take effect here)
3. ~~Internal resources~~ — removed (no bundled fallback)

## Implementation Steps

### Step 1: Relocate Bundled Prompt Files to `resources/config/prompts/`
- **File:** [src/teddy_executor/resources/prompts/](/src/teddy_executor/resources/prompts/) → [src/teddy_executor/resources/config/prompts/](/src/teddy_executor/resources/config/prompts/)
- **Change:** Move the 6 XML prompt files (`pathfinder.xml`, `architect.xml`, `developer.xml`, `debugger.xml`, `assistant.xml`, `prototyper.xml`) from `src/teddy_executor/resources/prompts/` to `src/teddy_executor/resources/config/prompts/`. Remove the now-empty `src/teddy_executor/resources/prompts/` directory and its `__init__.py`. Create `src/teddy_executor/resources/config/prompts/__init__.py` (empty file).

**Files to move:**
- `src/teddy_executor/resources/prompts/__init__.py` → (delete)
- `src/teddy_executor/resources/prompts/architect.xml` → `src/teddy_executor/resources/config/prompts/architect.xml`
- `src/teddy_executor/resources/prompts/assistant.xml` → `src/teddy_executor/resources/config/prompts/assistant.xml`
- `src/teddy_executor/resources/prompts/debugger.xml` → `src/teddy_executor/resources/config/prompts/debugger.xml`
- `src/teddy_executor/resources/prompts/developer.xml` → `src/teddy_executor/resources/config/prompts/developer.xml`
- `src/teddy_executor/resources/prompts/pathfinder.xml` → `src/teddy_executor/resources/config/prompts/pathfinder.xml`
- `src/teddy_executor/resources/prompts/prototyper.xml` → `src/teddy_executor/resources/config/prompts/prototyper.xml`

- **Related updates:** Remove `from . import prompts` from `src/teddy_executor/resources/__init__.py` if present. Update any import paths that referenced `teddy_executor.resources.prompts` to `teddy_executor.resources.config.prompts`.

### Step 2: `InitService` Copies Prompt XMLs to `.teddy/prompts/` During Init
- **File:** [src/teddy_executor/core/services/init_service.py](/src/teddy_executor/core/services/init_service.py)
- **Change:** After the existing `ensure_initialized` logic that copies `.gitignore`, `config.yaml`, and `init.context`, add a block that creates `.teddy/prompts/` directory and copies the 6 prompt XML files from the bundled resources (now at `resources/config/prompts/`). Follow the same pattern as the existing `_get_default_content` method:
  1. Check if `.teddy/prompts/` directory exists; if not, create it.
  2. For each prompt file (`pathfinder.xml`, `architect.xml`, `developer.xml`, `debugger.xml`, `assistant.xml`, `prototyper.xml`), check if it already exists in `.teddy/prompts/`. If not, copy from bundled resources using `_get_default_content` (or a new `_get_prompt_content` method that searches the prompts subdirectory).
  3. Handle missing bundled prompts gracefully (log a warning and skip; do not crash).

**Why conditional copy?** Users may have already edited prompts in `.teddy/prompts/` — never overwrite customizations.

### Step 3: Session Init Copies Prompt from `.teddy/prompts/` Instead of Internal Resources
- **File:** [src/teddy_executor/core/services/session_service.py](/src/teddy_executor/core/services/session_service.py)
- **Change:** In `SessionService.create_session()` (lines ~63–67), the prompt content is obtained via `self._prompt_manager.get_prompt_content(options.agent_name)`. This currently calls `find_prompt_content()` which reads from internal resources. Change this to read from `.teddy/prompts/<agent_name>.xml` instead. Use the `IFileSystemManager` port to read the file.

Specifically, replace:
```python
prompt_content = self._prompt_manager.get_prompt_content(options.agent_name)
```
with logic that first checks `.teddy/prompts/<agent_name>.xml`, and if not found, raises a `ValueError` with a clear message suggesting the user run `teddy init` to restore prompts.

- **Note:** The `_prompt_manager.get_prompt_content` method itself will be updated in Step 4 to resolve from `.teddy/prompts/`. But session_service should directly use the filesystem to read the prompt for robustness, as the method is also used for `teddy get-prompt`.

- **Also update:** `prompt_manager.py`'s `get_prompt_content` method should also be updated (Step 4 covers this). Ensure consistency.

### Step 4: `fetch_system_prompt` and `find_prompt_content` Resolve from `.teddy/prompts/` (Remove Internal Fallback)
- **File:** [src/teddy_executor/core/services/prompt_manager.py](/src/teddy_executor/core/services/prompt_manager.py)
- **Change:** In `PromptManager.fetch_system_prompt()`:
  1. Keep the first priority: session root (`turn_path.parent / f"{agent_name}.xml"`).
  2. Replace the second priority (internal resource path) with `.teddy/prompts/<agent_name>.xml`:
     ```python
     project_prompt = (turn_path.parent.parent.parent / ".teddy" / "prompts" / f"{agent_name}.xml").as_posix()
     ```
     Or better, resolve from `find_project_root()` (see `cli_helpers.py`) + `.teddy/prompts/`.
  3. Remove the `Path(__file__).parent.parent.parent / "resources" / "prompts" / ...` fallback entirely.
  4. If neither session root nor `.teddy/prompts/` contains the prompt, log a warning and return empty string.

- **File:** [src/teddy_executor/prompts.py](/src/teddy_executor/prompts.py)
- **Change:** Update `find_prompt_content(agent_name)` function. Currently it reads from `teddy_executor.resources.prompts` (internal resources). Change it to read from `.teddy/prompts/<agent_name>.xml` relative to the project root (using `find_project_root()` from `cli_helpers.py` or similar logic). If the file doesn't exist, return `None` (or raise an error). Remove the internal resource import/read logic.

**Important:** The `prompts.py` module is used by `teddy get-prompt` via `PromptManager.get_prompt_content()`. After this change, `teddy get-prompt` will show the user-editable version from `.teddy/prompts/` instead of the bundled version.

### Step 5: Update Tests to Reflect New Prompt Resolution
- **Location:** All test files that reference prompt resolution, notably `test_prompt_manager.py`, `test_session_service.py`, `test_session_service_prompt_contract.py`, and any acceptance test that checks `get-prompt` output.
- **Changes:**
  1. Update tests that mock `find_prompt_content` or internal resource paths to instead point to a test fixture `.teddy/prompts/` directory.
  2. Ensure `InitService` tests verify prompt XMLs are copied to `.teddy/prompts/` during init.
  3. Ensure `fetch_system_prompt` tests verify the new resolution order: session root → `.teddy/prompts/` (no internal fallback).
  4. Add a test that `teddy get-prompt` returns content from `.teddy/prompts/` after init.

## Verification

1. `teddy init` creates `.teddy/prompts/` with all 6 prompt XML files (check via `ls .teddy/prompts/`).
2. `teddy get-prompt pathfinder` returns the content from `.teddy/prompts/pathfinder.xml`, not a bundled version.
3. Editing `.teddy/prompts/pathfinder.xml` and starting a new session (`teddy start --session -a pathfinder`) causes the session root prompt to reflect the edited content.
4. Existing sessions (pre-migration) retain their prompt snapshot in the session root.
5. If prompts are missing from `.teddy/prompts/` (e.g., deleted manually), `teddy init` restores missing ones without overwriting existing ones.
6. `fetch_system_prompt` returns session root prompt first, then `.teddy/prompts/`, and does NOT fall back to internal resources.
7. All existing tests pass, particularly `test_prompt_manager.py`, `test_session_service_prompt_contract.py`, and `test_init_service.py`.
8. No references to `teddy_executor.resources.prompts` remain in the codebase (except potentially in git history).
