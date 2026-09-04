# Slice: 03-01-Editor-Validation-and-Discovery
- **Status:** Planned
- **Milestone:** [03-Foundational-Refactors](/docs/project/milestones/03-foundational-refactors.md)
- **Specs:** [Editor Validation & Discovery](/docs/project/specs/editor-validation-and-discovery.md)
- **Component Docs:** ConsoleToolingHelper (add), YamlConfigAdapter (update), IConfigService (update), session_cli_handlers (update)
- **Scope Slug:** `editor-validation-and-discovery`

## Business Goal
Eliminate silent editor failures by validating editor configuration early at session startup. When the configured editor is missing or unconfigured, automatically discover available editors from PATH and prompt the user to select one, persisting the result to `.teddy/config.yaml`. Support a "disabled" sentinel for graceful disablement and provide reliable diff viewer fallback for unknown editors.

## Scenarios

> As a user, I want my configured editor to be validated at session start so that I know it's missing before I need it.
```gherkin
Given an interactive session is started
And the editor "code" is configured in .teddy/config.yaml
But "code" is not in PATH
When the preflight check runs
Then a warning is displayed: "Configured editor 'code' not found in PATH. Discovering alternatives..."
And the available editors from PATH are listed for selection
```

> As a user, I want to discover available editors when none is configured so that I can choose one without guessing names.
```gherkin
Given an interactive session is started
And no editor is configured (editor: "")
When the preflight check runs
Then a message is displayed: "No editor configured. Scanning for available editors in PATH..."
And known editors are discovered via which()
And a numbered list of found editors is displayed
And I can select one by number
And the selection is saved to .teddy/config.yaml
```

> As a user, I want to use a custom editor not in the known list so that I have full flexibility.
```gherkin
Given the preflight editor discovery prompt is shown
When I type a custom editor command not in the known list
Then the command is validated with which()
If valid, it is saved to config
If invalid, I am prompted again until a valid command or empty input is given
```

> As a user, I want to disable editor functionality so that I am never prompted to configure one.
```gherkin
Given the preflight editor discovery prompt is shown
When I leave the input empty
Then "disabled" is saved as the editor value in .teddy/config.yaml
And find_editor() returns None everywhere
And log messages inform me that the editor is disabled
```

> As a user, I want the "disabled" sentinel to be respected so that editor functionality is gracefully disabled everywhere.
```gherkin
Given the editor is set to "disabled" in config
When find_editor() is called
Then it returns None without checking env vars
And ConsoleAskLoop._launch_editor_background() logs "Editor is disabled in config"
And returns empty string
```

> As a user, I want a diff viewer that works with unknown editors so that I can review diffs even without registered diff flags.
```gherkin
Given a configured editor "my_editor" that is not in _DIFF_FLAGS
When get_diff_viewer_command() is called
Then it returns [resolved_editor_path] with no flags
And the caller passes both file paths as arguments
```

> As a user, I want the diff_flags config to override the built-in translation table so that I can force custom flags.
```gherkin
Given the editor is "nvim"
And the config has diff_flags: ["--diff", "--wait"]
When get_diff_viewer_command() is called
Then it returns ["/path/to/nvim", "--diff", "--wait"]
And the _DIFF_FLAGS value of ["-d"] is overridden
```

> As a user, I want to skip editor validation in non-interactive mode so that scripts and pipelines never block on prompts.
```gherkin
Given a non-interactive session (--yolo/--pipeline/--yes)
When the preflight check runs
Then _validate_editor_config() is NOT called
And no editor prompts are shown
```

## Edge Cases
- **User disables after setting prompts**: If the user explicitly set "disabled" in config between sessions, the preflight check skips validation entirely (no warning, no prompt).
- **Env var fallback bypassed by "disabled"**: When "disabled" is set, find_editor() returns None immediately — does NOT fall through to VISUAL/EDITOR env vars.
- **Config file missing during set_setting**: YamlConfigAdapter.set_setting() creates the config file if it doesn't exist.
- **YAML merge preserves comments**: yaml.dump() strips comments. The user-facing comment in config.yaml is only in the baseline (bundled) config, not the user config. set_setting() only writes to the user config file — this is acceptable.
- **Empty editor string vs "disabled"**: Both result in the same preflight check behavior (discovery prompt). The difference is that "disabled" persists the result of user explicitly declining, while empty string means "not yet configured."
- **TUI unknown editor classification**: The spec says unknown editors in TUI should route to annotated diff path (was GUI). This changes existing behavior for users with custom editors. The change means custom editors get the same unified diff experience as CLI editors.

## Key Unknowns
- [ ] [Technical] `YamlConfigAdapter.set_setting()` — The `_config_path` is set at construction time. For `root_dir`-based paths (used in session init), the path must already exist. set_setting() must handle `os.path.exists()` checks and directory creation if needed.
- [ ] [Technical] `_DIFF_FLAGS` expansion — The spec lists 15 flags entries. Some JetBrains editors (webstorm, phpstorm, etc.) use `"diff"` (no dash prefix) while `code`, `cursor`, etc. use `"--diff"`. Verify this convention works correctly when invoked via subprocess.
- [ ] [Technical] Unknown editor fallback impact on TUI — Currently unknown editors route to GUI path (before/after files + ConfirmScreen). Changing to annotated diff path changes the user experience: they lose the ability to compare files side-by-side in a GUI. The diff_flags config override gives power users a way to restore GUI behavior.

## Implementation Plan
The spec defines 5 phases which map to deliverables following the Tracer Bullet Dependency Sequence: Contract → Harness → Seam → Wiring → Logic → Migration → Refactor → Cleanup. The key architectural changes are:

1. `IConfigService` adds `set_setting()` abstract method (breaking change)
2. `ConsoleToolingHelper` adds `discover_editors()`, `KNOWN_EDITORS`, sentinel handling, fallback logic
3. `YamlConfigAdapter` implements `set_setting()` with dot-notation YAML persistence
4. `session_cli_handlers.py` adds `_validate_editor_config()` + prompting functions, modifies `_run_cli_preflight_check()` with `interactive` flag
5. `config.yaml` default editor changed to empty string with updated comments
6. `textual_plan_reviewer_editor.py` unknown editor routing changed to annotated diff path
7. `console_interactor_ask_loop.py` adds log messages for disabled sentinel
8. `_DIFF_FLAGS` expanded with all entries from spec

The deliverable dependency structure ensures each step is testable:
- **Contract** deliverables must come first (interfaces defined before implementations)
- **Harness** deliverables test the interfaces after contracts are defined but before wiring
- **Wiring** deliverables connect components end-to-end with trivial/hardcoded data
- **Logic** deliverables replace trivial implementations with real rules via TDD
- **Migration** deliverables update existing consumers to use new interfaces/behavior

## Deliverables

- [ ] **Contract** — Add `set_setting(key: str, value: Any) -> None` abstract method to `IConfigService` protocol in `config_service.py`
- [ ] **Contract** — Change default editor from `"code"` to `""` in `config.yaml` with updated comments (add `diff_flags` section)
- [ ] **Harness** — Add `KNOWN_EDITORS` fixture and mock `discover_editors` patterns to `test_console_tooling_editor.py`
- [ ] **Harness** — Update `IConfigService` mock in test harness (mocking.py, composition.py) to implement `set_setting()`
- [ ] **Seam** — Add `KNOWN_EDITORS: list[str]` class-level constant to `ConsoleToolingHelper` (as specified in spec 2a)
- [ ] **Wiring** — Add `discover_editors() -> list[tuple[str, str]]` method to `ConsoleToolingHelper` with PATH scanning and deduplication
- [ ] **Wiring** — Modify `find_editor()` to handle "disabled" sentinel (returns None immediately, bypasses env fallback)
- [ ] **Wiring** — Extend `_DIFF_FLAGS` translation table with all entries from spec 2d (add idea, webstorm, phpstorm, pycharm, rubymine, goland, clion, fleet)
- [ ] **Logic** — Implement `YamlConfigAdapter.set_setting()` with dot-notation support, file creation, cache update, and YAML persistence
- [ ] **Logic** — Implement `get_diff_viewer_command()` unknown editor fallback: return `[editor_path]` with no flags when editor not in `_DIFF_FLAGS`
- [ ] **Logic** — Implement `get_diff_viewer_command()` `diff_flags` config override: use config value instead of `_DIFF_FLAGS` when `diff_flags` key is set
- [ ] **Migration** — Add `_validate_editor_config(container)` function to `session_cli_handlers.py` with discovery and prompting flow
- [ ] **Migration** — Add `_prompt_for_editor_selection()` and `_prompt_for_custom_editor()` prompting functions with `typer.prompt()` input validation
- [ ] **Migration** — Modify `_run_cli_preflight_check()` to accept `interactive: bool = True` parameter and call `_validate_editor_config()` when interactive
- [ ] **Migration** — Wire `interactive` flag from `handle_new_session()` and `handle_resume_session()` through to `_run_cli_preflight_check()`
- [ ] **Migration** — Change `preview_edit_diff_viewer()` in `textual_plan_reviewer_editor.py`: unknown editors (not in `_DIFF_FLAGS`) route to annotated diff path instead of GUI before/after path
- [ ] **Migration** — Add log message "Editor is disabled in config" to `ConsoleAskLoop._launch_editor_background()` and `ConsoleInteractorAdapter._launch_editor_synchronous()` when `find_editor()` returns None
- [ ] **Wiring** — Add behavioral tests for the complete preflight check flow (editor validation integration): mock `discover_editors`, verify `set_setting` is called with correct values

## Implementation Notes
*(Filled by the Developer during implementation.)*

## Verification
- [ ] Start a new interactive session with no editor configured → see discovery prompt
- [ ] Select a numbered editor → verify it's written to `.teddy/config.yaml`
- [ ] Start a new session with the saved editor → no prompt shown (editor found in PATH)
- [ ] Start a session with a missing configured editor → see warning + discovery fallback
- [ ] Start a session with `editor: "disabled"` → no prompt, find_editor() returns None everywhere
- [ ] Start a session with `--yolo` flag → editor validation is skipped entirely
- [ ] Press `e` in ask loop with editor disabled → see "Editor is disabled in config" log
- [ ] Press `e` on an EDIT action in TUI with an unknown editor → annotated diff opens instead of GUI path
- [ ] Set `diff_flags` in config → verify get_diff_viewer_command() returns custom flags
- [ ] Set editor to a known CLI editor → verify get_diff_viewer_command() returns correct diff flags
