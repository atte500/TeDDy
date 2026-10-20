# Component Design: ConsoleToolingHelper
- **Status:** Implemented
- **Source:** [`src/teddy_executor/adapters/outbound/console_tooling.py`](/src/teddy_executor/adapters/outbound/console_tooling.py)

## Purpose
A utility that centralizes editor and diff-viewer discovery. It locates editor executables on `PATH`, resolves the configuration preference, honors the `disabled` sentinel, and maps editors to their diff-viewer flags.

## Consumers
- **`ConsoleInteractorAdapter`** (`teddy_executor.adapters.outbound.console_interactor`): Resolves the editor and diff viewer for prompts and previews.
- [`TextualPlanReviewer`](../inbound/textual_plan_reviewer.md): Resolves the editor for context-aware editing in the TUI.
- **`session_cli_handlers`** (`teddy_executor.adapters.inbound.session_cli_handlers`): Validates the configured editor during preflight.

## Dependencies
- [`ISystemEnvironment`](../../core/ports/outbound/system_environment.md): Provides `which()` and `get_env()`.
- [`IConfigService`](../../core/ports/outbound/config_service.md): Provides `get_setting()` for the `editor` and `diff_flags` keys.
- **`normalize_editor_basename`** (`teddy_executor.core.utils.editor_names`): Strips Windows launcher suffixes and lowercases the editor basename before the `_DIFF_FLAGS` lookup.

## Class Invariants
- `constant_editor_list`: `KNOWN_EDITORS` is a class-level constant list and is never modified at runtime.
- `constant_diff_flags`: `_DIFF_FLAGS` is a class-level constant dictionary and is never modified at runtime.
- `injected_collaborators`: `_system_env` and `_config_service` are never `None` after construction.

## Inbound Ports
None — this is a utility service injected into adapters through constructor injection.

## Outbound Ports
- **`ISystemEnvironment`**: Consumed for command resolution and environment reads.
- **`IConfigService`**: Consumed for the `editor` and `diff_flags` settings.

## Data Contracts
- **`KNOWN_EDITORS`** (`list[str]`): The curated editor list scanned by `discover_editors()`, ordered terminal editors first, then GUI and IDE editors.
- **`_DIFF_FLAGS`** (`dict[str, list[str]]`): Maps editor basenames to diff-viewer flags. Known entries include `vim`, `vi`, and `nvim` (`-d`), `code`, `cursor`, `codium`, and `zed` (`--diff`), and the JetBrains family (`diff`).
- **`discover_editors` return:** A list of `(basename, resolved_path)` pairs, deduplicated by resolved path.

## Operations

### `discover_editors() -> list[tuple[str, str]]`
- **Postconditions:** Returns every `KNOWN_EDITORS` entry resolved on `PATH`, deduplicated by resolved path and ordered by the `KNOWN_EDITORS` sequence. Returns an empty list when no known editor is found.

### `find_editor() -> Optional[list[str]]`
- **Postconditions:** Returns the resolved editor command. Priority: the `disabled` sentinel returns `None` immediately without consulting the environment; the config `editor` value; then the `VISUAL` or `EDITOR` environment variable; then `None`.

### `get_diff_viewer_command() -> Optional[list[str]]`
- **Postconditions:** Returns a diff-viewer command. Priority: a valid `diff_flags` config list prepended with the editor path; the `TEDDY_DIFF_TOOL` environment variable; the `_DIFF_FLAGS` translation table; then the editor path with no flags for an unknown editor. Returns `None` when no editor or tool is found. A `diff_flags` value that is not a list is skipped, and a configured `TEDDY_DIFF_TOOL` that is not found returns `None` with no fallback. The editor basename is normalized through the shared helper before the `_DIFF_FLAGS` lookup, so a resolved `codium.CMD` still maps to the `--diff` entry instead of the flagless fallback.

### `_resolve_editor_cmd(editor_str) -> Optional[list[str]]`
- **Preconditions:** `editor_str` is `None` or a non-empty string.
- **Postconditions:** Parses the string with `shlex.split`, expands a leading `~`, resolves the first token through `which()`, and returns the command list. Returns `None` when the executable is not found.
