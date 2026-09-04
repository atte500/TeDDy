# Component Design: ConsoleToolingHelper

**Status:** Planned

## Purpose / Responsibility

The `ConsoleToolingHelper` is a utility service that provides centralized discovery and resolution of external editors and diff viewers. It abstracts the logic of locating editor executables on `PATH`, resolving configuration preferences, handling the "disabled" sentinel, and mapping editors to their appropriate diff viewer flags.

## Failure Modes

- **Unconfigured editor returns None**: When `editor` config is empty and no `VISUAL`/`EDITOR` env var is set, `find_editor()` returns `None`. This is a valid state; callers MUST handle `None` gracefully (e.g., log a message, skip editor launch).
- **"disabled" sentinel bypasses env fallback**: If `editor` is set to `"disabled"`, `find_editor()` returns `None` immediately without checking `VISUAL`/`EDITOR` env vars. This is intentional — the user explicitly disabled editor functionality.
- **Unknown editor with diff viewer**: `get_diff_viewer_command()` returns the editor path with no flags for editors not in `_DIFF_FLAGS`. The caller MUST pass both file paths as separate arguments for the editor to open in separate tabs.
- **`diff_flags` config override must be validated**: If `diff_flags` config key is set but is not a list of strings, `get_diff_viewer_command()` MUST skip the override and fall through to the translation table. This prevents crashes from malformed config values.
- **`TEDDY_DIFF_TOOL` takes precedence over all**: When the env var is set, `get_diff_viewer_command()` uses it directly, bypassing `_DIFF_FLAGS` translation and config override. If the tool is not found via `which()`, returns `None` (no fallback to editor flags).

## Class Invariants

- `_DIFF_FLAGS` is a class-level constant dictionary that MUST NOT be modified at runtime.
- `KNOWN_EDITORS` is a class-level constant list that MUST NOT be modified at runtime.
- `_system_env` and `_config_service` MUST NOT be `None` after initialization.

## Ports

- **Type:** Utility service (injected into adapters via constructor injection)
- **Dependencies:**
  - `ISystemEnvironment` — for `which()`, `get_env()` methods
  - `IConfigService` — for `get_setting()` and `set_setting()` methods
- **Consumed By:**
  - `ConsoleInteractorAdapter` (via `ConsoleAskLoop`)
  - `TextualPlanReviewer` (via `ReviewerApp._console_tooling`)
  - `session_cli_handlers` (for preflight editor validation)

## Implementation Details / Logic

### Editor Discovery (`discover_editors`)

Scans `PATH` for all executables in `KNOWN_EDITORS` using `ISystemEnvironment.which()`. Deduplicates by resolved path (same binary under different aliases). Returns list of `(basename, resolved_path)` tuples sorted by the order in `KNOWN_EDITORS`.

### Editor Resolution (`find_editor`)

Priority chain:
1. **Check for "disabled" sentinel**: If `config_service.get_setting("editor")` returns `"disabled"` (case-insensitive, stripped), return `None` immediately.
2. **Config value**: If config has a non-empty editor string, resolve it via `_resolve_editor_cmd()`. If found, return the command list.
3. **Env var fallback**: Check `VISUAL` then `EDITOR`. If found, resolve and return.
4. **Return None**: No editor found.

### Diff Viewer Command (`get_diff_viewer_command`)

Priority chain:
1. **`diff_flags` config override**: If `config_service.get_setting("diff_flags")` returns a list, prepend the resolved editor path from `find_editor()` and return `[editor_path] + diff_flags`.
2. **`TEDDY_DIFF_TOOL` env var**: Parse with `shlex.split()`, resolve the first word via `which()`, return the full command.
3. **Translation table**: Resolve editor via `find_editor()`, extract basename, look up in `_DIFF_FLAGS`. If found, return `[editor_path] + flags`.
4. **Unknown editor fallback**: Return `[editor_path]` with no flags. The caller passes both file paths as arguments, so the editor opens both files in separate tabs (reliable no-guess fallback).
5. **Return None**: No editor found, no env var set.

## Data Contracts / Methods

### `KNOWN_EDITORS`
- **Type:** `class-level constant: list[str]`
- **Preconditions:** None (static constant).
- **Postconditions:** Contains a comprehensive list of known editor executable names (terminal and GUI).

### `_DIFF_FLAGS`
- **Type:** `class-level constant: dict[str, list[str]]`
- **Preconditions:** None (static constant).
- **Postconditions:** Maps editor basenames to their correct diff viewer flags. Known entries: vim(-d), vi(-d), nvim(-d), code(--diff), cursor(--diff), codium(--diff), zed(--diff), idea(diff), idea.sh(diff), webstorm(diff), phpstorm(diff), pycharm(diff), rubymine(diff), goland(diff), clion(diff), fleet(diff).

### `discover_editors() -> list[tuple[str, str]]`
- **Preconditions:** `KNOWN_EDITORS` must be defined. `ISystemEnvironment.which()` must resolve executables from PATH.
- **Postconditions:** Returns a list of `(basename, resolved_path)` pairs. Deduplicates by resolved path. May return empty list if no known editors are on PATH.
- **Exceptions:** None (returns empty list on failure).
- **Invariants:** `KNOWN_EDITORS` is not modified.

### `find_editor() -> Optional[list[str]]`
- **Preconditions:** `_config_service` and `_system_env` must be initialized.
- **Postconditions:** Returns a list of strings (editor command) if a valid editor is found, `None` otherwise. If config value is `"disabled"`, returns `None` without checking env vars.
- **Exceptions:** None (returns `None` on failure).
- **Invariants:** The "disabled" sentinel bypasses env fallback.

### `get_diff_viewer_command() -> Optional[list[str]]`
- **Preconditions:** `_config_service` and `_system_env` must be initialized.
- **Postconditions:** Returns a command list for invoking a diff viewer. Priority: `diff_flags` config override > `TEDDY_DIFF_TOOL` env var > `_DIFF_FLAGS` translation table > unknown editor fallback (editor path only, no flags). Returns `None` if no editor or diff tool is found.
- **Exceptions:** None (returns `None` on failure).
- **Invariants:** `diff_flags` config override is validated to be a list; invalid types are skipped.

### `_resolve_editor_cmd(editor_str: Optional[str]) -> Optional[list[str]]`
- **Preconditions:** `editor_str` may be `None` or a non-empty string.
- **Postconditions:** If `editor_str` is non-empty and its first token resolves via `which()`, returns a command list with the resolved path. Returns `None` otherwise.
- **Exceptions:** None.
