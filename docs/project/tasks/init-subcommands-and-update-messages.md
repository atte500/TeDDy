# Task: `teddy init` Subcommands & Update Message Cleanup

## Business Goal
Provide a safe, explicit way to refresh bundled prompts and config files after upgrades, and remove outdated instructions about manual prompt folder deletion.

## Context

### Current State
- `teddy init` writes config files (config.yaml, .gitignore, init.context) and prompt XMLs only if they don't already exist.
- The `update` command (`__main__.py:189-226`) prints: `"To apply prompt updates: delete .teddy/prompts/ and run 'teddy init'"` in both the experimental and stable code paths.
- The startup notification (displayed in session start/resume) likely contains similar text (see `update_checker.py`).
- README mentions only `teddy init` as the initialization command, with no subcommands.
- `IInitUseCase.ensure_initialized()` returns `None` — no status information for logging.

### Required Changes
1. **Add subcommands** `teddy init prompts` and `teddy init config` that always overwrite their respective files.
2. **Add logging** to `teddy init` alone: after execution, log whether config and/or prompts were updated or unchanged.
3. **Extend `IInitUseCase`** with methods for prompts and config subcommands that return status strings.
4. **Update `teddy update`** to no longer say "delete .teddy/prompts/ and run 'teddy init'".
5. **Update update checker** (startup notification) to remove the same message.
6. **Update README** to document the new subcommands and remove manual deletion instructions.

## Implementation Steps

### Step 1: Extend `IInitUseCase` port
- **File:** [src/teddy_executor/core/ports/inbound/init.py](/src/teddy_executor/core/ports/inbound/init.py)
- **Change:** Add two new abstract methods:
  - `ensure_prompts_initialized(overwrite: bool = False) -> str` — returns a human-readable status (e.g., "Prompts overwritten (6 files).").
  - `ensure_config_initialized(overwrite: bool = False) -> str` — returns a human-readable status (e.g., "Configuration files overwritten (3 files).").
  - Modify `ensure_initialized()` return type from `None` to `str` to return a summary (e.g., "Config: unchanged. Prompts: updated (3 files).").
  - Update the ABC signature accordingly.

### Step 2: Update `InitService`
- **File:** [src/teddy_executor/core/services/init_service.py](/src/teddy_executor/core/services/init_service.py)
- **Change:**
  - Rename `_init_prompts` to `_init_prompts(self, overwrite: bool = False) -> str` that:
    - If `overwrite=True`, always writes prompt files and returns "Prompts overwritten (N files)."
    - If `overwrite=False` (current behavior), writes only missing files and returns "Prompts unchanged." if none were written, or "Prompts updated (N files)." if some were.
  - Add `_init_config_dir(self, overwrite: bool = False) -> str` that handles config.yaml, .gitignore, and init.context with the same overwrite logic.
  - Modify `ensure_initialized()` to call `_init_config_dir(overwrite=False)` and `_init_prompts(overwrite=False)`, collect their return strings, and build a combined summary like "Config: unchanged. Prompts: updated (3 files)."
  - Implement `ensure_prompts_initialized(overwrite: bool = True) -> str` that delegates to `_init_prompts(overwrite=overwrite)`.
  - Implement `ensure_config_initialized(overwrite: bool = True) -> str` that delegates to `_init_config_dir(overwrite=overwrite)`.
  - Update the `_get_default_content` method to not silently swallow errors; replace bare `except: pass` with specific catch of `(OSError, yaml.YAMLError, ImportError, AttributeError)` and log a debug message before returning `None`. (This also addresses existing Technical Debt noted in PROJECT.md.)

### Step 3: Restructure CLI `init` command as Typer subcommand group
- **File:** [src/teddy_executor/__main__.py](/src/teddy_executor/__main__.py)
- **Change:**
  - Remove the existing `@app.command()` for `init` (lines 118-129).
  - Create a new Typer app: `init_app = typer.Typer()`.
  - Register it with the main app: `app.add_typer(init_app, name="init")`.
  - Define three callbacks:
    - **`@init_app.callback(invoke_without_command=True)`**: runs the current "init everything" logic but now prints the summary string returned by `ensure_initialized()`.
    - **`@init_app.command()` for `prompts`**: calls `ensure_prompts_initialized(overwrite=True)` and prints the status.
    - **`@init_app.command()` for `config`**: calls `ensure_config_initialized(overwrite=True)` and prints the status.
  - Ensure the `prewarm_imports()` call remains after initialization in all code paths.
  - Keep the existing `typer.echo("TeDDy initialized in .teddy folder.")` for the bare `init` command (or replace with the summary from the service).

### Step 4: Update `teddy update` command messages
- **File:** [src/teddy_executor/__main__.py](/src/teddy_executor/__main__.py)
- **Change:** In both the experimental and stable branches of the `update` command, replace:
  ```python
  typer.echo("To apply prompt updates: delete .teddy/prompts/ and run 'teddy init'")
  ```
  with:
  ```python
  typer.echo("To apply prompt updates, run: teddy init prompts")
  ```

### Step 5: Update update checker startup notification
- **File:** [src/teddy_executor/core/services/update_checker.py](/src/teddy_executor/core/services/update_checker.py)
- **Change:** Find any string containing "delete .teddy/prompts/" and replace it with "run 'teddy init prompts'". If there is no such string, no change needed.

### Step 6: Update README
- **File:** [README.md](/README.md)
- **Change:**
  - In the "Initialize" section, add documentation for the new subcommands:
    ```markdown
    - `teddy init prompts` – Overwrite bundled prompt XMLs with defaults (useful after upgrades).
    - `teddy init config` – Overwrite config.yaml, .gitignore, and init.context with defaults.
    ```
  - Remove any references to manually deleting `.teddy/prompts/` (search for "delete .teddy/prompts").
  - Update the Command Reference table under "Getting Started" to include `init prompts` and `init config` rows.

### Step 7: Add/update unit tests
- **File:** [tests/suites/unit/core/services/test_init_service.py](/tests/suites/unit/core/services/test_init_service.py)
- **Change:** Add tests for:
  - `ensure_prompts_initialized(overwrite=True)` overwrites existing prompt files.
  - `ensure_config_initialized(overwrite=True)` overwrites existing config files.
  - `ensure_initialized()` returns a summary string reflecting what was skipped/written.
  - `ensure_initialized()` does not change existing files when they already exist (unchanged status).
  - `ensure_prompts_initialized(overwrite=False)` (default) only writes missing files.
  - `ensure_config_initialized(overwrite=False)` (default) only writes missing files.

### Step 8: Update existing acceptance tests if needed
- **File:** [tests/suites/acceptance/test_streamlined_init.py](/tests/suites/acceptance/test_streamlined_init.py) and any other tests calling `teddy init` via `CliRunner`
- **Change:** Ensure tests still pass with the new subcommand structure. The `teddy init` command's callback behavior should remain functionally identical for the no-arguments case.

## Verification

1. Run `teddy init` in a freshly cleaned environment → should create .teddy/ with all files, print summary "Config: updated (3 files). Prompts: updated (6 files)."
2. Run `teddy init` again → should print "Config: unchanged. Prompts: unchanged."
3. Run `teddy init prompts` → should overwrite all 6 prompt XMLs, print "Prompts overwritten (6 files)."
4. Run `teddy init config` → should overwrite config.yaml, .gitignore, init.context, print "Configuration files overwritten (3 files)."
5. Run `teddy update` → should not mention "delete .teddy/prompts/" anywhere in output.
6. README should list `init prompts` and `init config` in the Command Reference.
7. All existing unit tests in `test_init_service.py` pass.
8. All acceptance tests in `test_streamlined_init.py` pass.
9. Manual check: `teddy init prompts` after modifying a prompt file should replace it.
10. Manual check: `teddy init config` after modifying config.yaml should replace it (user warned: this resets config to defaults).
