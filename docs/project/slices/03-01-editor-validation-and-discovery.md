# Slice: 03-01-Editor-Validation-and-Discovery
- **Status:** In Progress
- **Milestone:** [03-Foundational-Refactors](/docs/project/milestones/03-foundational-refactors.md)
- **Specs:** [Editor Validation & Discovery](/docs/project/specs/editor-validation-and-discovery.md)
- **Prototype:** [spikes/prototypes/editor-validation-and-discovery/](/spikes/prototypes/editor-validation-and-discovery/)
- **Component Docs:** [ConsoleToolingHelper](/docs/architecture/adapters/outbound/console_tooling.md) (add), [YamlConfigAdapter](/docs/architecture/adapters/outbound/yaml_config_adapter.md) (update), [IConfigService](/docs/architecture/core/ports/outbound/config_service.md) (update), [CLI Adapter](/docs/architecture/adapters/inbound/cli.md) (update)
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
- **Config file/directory missing during set_setting**: If the user config file does not exist, YamlConfigAdapter.set_setting() creates it. If the PARENT directory (e.g., `.teddy/` for a `root_dir`-based adapter) does not exist, it is created recursively via `os.makedirs(..., exist_ok=True)` BEFORE the write — otherwise the write raises `FileNotFoundError` (spike-verified, `probe_ku1`).
- **Stale cache after set_setting**: After a write, the in-memory merged `_config` cache MUST be updated in place so a subsequent `get_setting()` on the SAME adapter returns the new value. A disk-only write leaves the cache stale, returning the pre-write value (spike-verified, `probe_ku1`).
- **YAML merge preserves comments**: yaml.dump() strips comments. The user-facing comment in config.yaml is only in the baseline (bundled) config, not the user config. set_setting() only writes to the user config file — this is acceptable.
- **Empty editor string vs "disabled"**: Both result in the same preflight check behavior (discovery prompt). The difference is that "disabled" persists the result of user explicitly declining, while empty string means "not yet configured."
- **TUI unknown editor classification**: The spec says unknown editors in TUI should route to annotated diff path (was GUI). This changes existing behavior for users with custom editors. The change means custom editors get the same unified diff experience as CLI editors.

## Key Unknowns
- [x] [Technical] `YamlConfigAdapter.set_setting()` — RESOLVED via `spikes/prototypes/editor-validation-and-discovery/spike.py` (`probe_ku1`). Three findings: (1) the spec's proposed body (§3) raises `FileNotFoundError` when the `root_dir`-based parent (`.teddy/`) does not yet exist, so `os.makedirs(os.path.dirname(self._config_path), exist_ok=True)` is REQUIRED before writing; (2) a disk-only write leaves the in-memory merged `_config` cache STALE (a fresh adapter read back `'nvim'` while the original adapter's `get_setting()` still returned `'code'`), so `set_setting()` MUST also update the in-memory `_config` cache in place; (3) with BOTH fixes the value persists to disk and reloads correctly via a fresh adapter, for `root_dir`-based paths AND plain deeply-nested (`nested/deep/config.yaml`) paths, including dot-notation keys. → The Spec §3 `set_setting` body MUST be corrected to add directory creation + cache update (Phase 4).
- [x] [Technical] `_DIFF_FLAGS` expansion — RESOLVED via `probe_ku2`. The bare `"diff"` convention is mechanically sound: the live `idea` entry resolved to `[<resolved_path>, "diff"]`, and `subprocess.run` transmitted `"diff"` as a discrete `argv[0]` element followed by the two file paths (observed launcher argv `["diff", <file1>, <file2>]`). Simulating the spec's 8 added JetBrains entries (`idea.sh`, `webstorm`, `phpstorm`, `pycharm`, `rubymine`, `goland`, `clion`, `fleet`) produced identical `[<path>, "diff"]` commands and `["diff", file1, file2]` argv. No dash prefix is needed; the convention works correctly through subprocess.
- [x] [Technical] Unknown editor fallback impact on TUI — RESOLVED via `probe_ku3`. CURRENT (pre-change) behaviour confirmed: an unknown editor (`my_editor`) takes the GUI before/after path (`create_temp=1`, `run_command=1`, no suspend), while a known CLI editor (`nvim`) takes the annotated path (`suspend=1`, no temp/run_command) and a known GUI editor (`code --diff`) takes the GUI path. The proposed routing predicate — `_is_cli_editor(diff_viewer) or basename(diff_viewer[0]).lower() not in _DIFF_FLAGS` — evaluates cli→annotated, known_gui→not-annotated, unknown→annotated, i.e. it correctly re-routes the unknown editor to the annotated diff path. This confirms the required migration change to `preview_edit_diff_viewer()`. NOTE (routing vs. override): the routing predicate reads the STATIC `_DIFF_FLAGS` table (not the resolved `get_diff_viewer_command()` output), so an unknown editor is routed to the annotated diff path regardless of whether `diff_flags` is configured in config. A user who wants the GUI before/after path must configure a known GUI editor whose basename is registered in `_DIFF_FLAGS` (e.g., `code`). The `diff_flags` config override changes only the FLAGS passed to the viewer, not the TUI routing decision.
- [x] [Functional] Console editor-selection UI — RESOLVED via `spikes/prototypes/editor-validation-and-discovery/editors_demo.py` (interactive; `--selftest` 18/18 pass; raw renders captured Turns 15 & 17). USER-APPROVED render: an ALWAYS-PRESENT header `Editor Setup` (cyan, bold) on BOTH branches; discovered editors listed one per line in **bracket** format with resolved paths HIDDEN (`[1] nvim`); a SINGLE primary prompt `Select an editor [1-{n}] (number, custom command, or empty to disable): `; valid number → save the resolved absolute PATH; out-of-range/invalid number → red `'{raw}' is not a valid selection. Choose 1-{n}.` then re-prompt; custom command → validated via `which()`, saved AS TYPED when available else red `'{raw}' was not found in PATH.` then re-prompt (custom commands are NEVER accepted without passing `which()` — explicit user requirement); empty → `"disabled"`; EOF → `"disabled"`; nothing-found → header + `No known editors found. Enter a custom editor command (leave empty to disable):` with the same validation loop. Colour ON (yellow warning / cyan header / green confirmation / red invalid), ALL output on stderr. Save confirmation is `Editor preference saved to .teddy/config.yaml.` (the trailing "Edit it directly at any time." clause was REMOVED per Showcase feedback). Folded into spec §4.

## Implementation Plan
The spec defines 5 phases which map to deliverables following the Tracer Bullet Dependency Sequence: Contract → Harness → Seam → Wiring → Logic → Migration → Refactor → Cleanup. The key architectural changes are:

1. `IConfigService` adds `set_setting()` abstract method (breaking change)
2. `ConsoleToolingHelper` adds `discover_editors()`, `KNOWN_EDITORS`, sentinel handling, fallback logic
3. `YamlConfigAdapter` implements `set_setting()` with dot-notation YAML persistence, recursive parent-directory creation (`os.makedirs`), and in-memory `_config` cache synchronization (all three spike-verified — see Prototype Findings)
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

### Prototype Findings (spike-verified, Slice 03-01)
Prototype: [spikes/prototypes/editor-validation-and-discovery/](/spikes/prototypes/editor-validation-and-discovery/) — `spike.py`, run with `uv run python spikes/prototypes/editor-validation-and-discovery/spike.py` (exit 0; 10/10 assertions pass).

- **KU1 — `set_setting()` (`probe_ku1`):** Both fixes are MANDATORY. (a) The original spec body raised `FileNotFoundError` when the `root_dir`-based `.teddy/` parent did not exist → `os.makedirs(os.path.dirname(self._config_path), exist_ok=True)` is required BEFORE the write. (b) A disk-only write left the in-memory merged `_config` cache stale (a fresh adapter read `'nvim'`; the SAME adapter's `get_setting()` still returned `'code'`) → `set_setting()` MUST also update `_config` in place. With both fixes, values persist and reload for `root_dir`-based AND plain deeply-nested (`nested/deep/config.yaml`) paths, including dot-notation keys. Spec §3 has been corrected accordingly.
- **KU2 — `_DIFF_FLAGS` JetBrains `"diff"` (`probe_ku2`):** The bare `"diff"` token (no dash) is transmitted as a discrete `argv` element through `subprocess.run` (observed launcher argv `["diff", <file1>, <file2>]`). All 8 planned JetBrains entries behave identically; no dash prefix is needed.
- **KU3 — TUI unknown-editor routing (`probe_ku3`):** CURRENT behaviour routes an unknown editor (`my_editor`) to the GUI before/after path (create_temp=1, run_command=1, no suspend). The proposed predicate (`_is_cli_editor(...) or basename(diff_viewer[0]).lower() not in _DIFF_FLAGS`) correctly re-routes the unknown editor to the annotated diff path while preserving known-GUI behaviour. The routing predicate reads the STATIC `_DIFF_FLAGS` table, so the `diff_flags` config override does NOT alter routing (it changes only the flags passed to the viewer).
- **Console editor-selection UI (`editors_demo.py`, `--selftest` 18/18):** the finalized, user-approved render is captured in spec §4 — always-on `Editor Setup` header; bracket list with hidden paths; a single primary prompt; red invalid-selection / invalid-custom messages that re-prompt; custom commands validated via `which()` (never accepted without it); empty/EOF → `"disabled"`; and the trimmed save confirmation `Editor preference saved to .teddy/config.yaml.`

### Impact Audit (Shared-Seam Analysis)
`git grep` census (Turns 5-6). `IConfigService` has many production consumers (a **Shared Seam** by the >1-consumer rule), but the `set_setting` change is ADDITIVE (Expansion), not a rewrite.

- **Only production implementer:** `YamlConfigAdapter`. No other concrete subclass of `IConfigService` exists under `src/`.
- **Test doubles auto-absorb the new member:** every harness/test double is an auto-specced mock (`register_mock` → `POSIXPathMock(spec=port_type)`, `create_autospec(IConfigService)`, `MagicMock(spec=IConfigService)`). Specced mocks expose every attribute of their spec, so they gain `set_setting` automatically. No hand-rolled concrete `IConfigService` fake exists. → the Harness deliverable "update IConfigService mock" is a practical NO-OP (kept only as a guard).
- **CRITICAL atomic ordering:** `set_setting` is declared `@abstractmethod`. Adding it to the ABC WITHOUT implementing it in `YamlConfigAdapter` makes the adapter uninstantiable (`TypeError: Can't instantiate abstract class YamlConfigAdapter with abstract method set_setting`), turning red every test that constructs it (`test_yaml_config_adapter*.py`, `test_config_defaults.py`, `tests/harness/setup/real_adapter_mixin.py`). Therefore the **Contract** deliverable (abstract method) and the `YamlConfigAdapter.set_setting` implementation MUST ship as ONE atomic green-to-green unit — do NOT commit the abstract method on its own. (Alternative, if a smaller diff is preferred: land the ABC member first as a non-abstract `raise NotImplementedError` default, then implement, then flip to `@abstractmethod` — but the bundle is simpler and is the prescribed path.)
- **Only caller of `set_setting` (post-slice):** the preflight `_validate_editor_config` flow. No other consumer reads it, so no Migration sweep beyond the preflight wiring is required.
- **No components deleted/renamed:** all existing `find_editor` / `get_diff_viewer_command` call sites remain valid; no documentation hits become stale.

## Deliverables

- [x] **Contract** — Add `set_setting(key: str, value: Any) -> None` abstract method to `IConfigService` protocol in `config_service.py` (MUST land atomically with the `set_setting` Logic deliverable below — declaring the abstract method alone leaves `YamlConfigAdapter` uninstantiable and reds every adapter-constructing test; see Impact Audit)
- [x] **Contract** — Change default editor from `"code"` to `""` in `config.yaml` with updated comments (add `diff_flags` section)
- [x] **Harness** — Add `KNOWN_EDITORS` fixture and mock `discover_editors` patterns to `test_console_tooling_editor.py` *(SUPERSEDED during the Plan Audit — see Implementation Notes. The audit found `KNOWN_EDITORS` and `discover_editors` do not exist yet (they are introduced by the Seam and Wiring deliverables below), so this cannot be a standalone green-to-green unit; its intent is folded into those deliverables' test bundles. The existing `mock_env` fixture already supports `which()` mocking, so no standalone fixture is required.)*
- [x] **Harness** — Update `IConfigService` mock in test harness (mocking.py, composition.py) to implement `set_setting()` *(verified NO-OP — see Impact Audit: every `IConfigService` double is auto-specced (`register_mock` → `POSIXPathMock(spec=port_type)`, `create_autospec`, `MagicMock(spec=IConfigService)`) and absorbs `set_setting` from the spec automatically; no hand-rolled concrete fake exists. Kept only as a guard.)*
- [ ] **Seam** — Add `KNOWN_EDITORS: list[str]` class-level constant to `ConsoleToolingHelper` (as specified in spec 2a)
- [ ] **Wiring** — Add `discover_editors() -> list[tuple[str, str]]` method to `ConsoleToolingHelper` with PATH scanning and deduplication
- [ ] **Wiring** — Modify `find_editor()` to handle "disabled" sentinel (returns None immediately, bypasses env fallback)
- [ ] **Wiring** — Extend `_DIFF_FLAGS` translation table with all entries from spec 2d (add idea, webstorm, phpstorm, pycharm, rubymine, goland, clion, fleet)
- [x] **Logic** — Implement `YamlConfigAdapter.set_setting()` with dot-notation support, file creation, cache update, and YAML persistence
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

### Deliverables #1 (Contract) + #9 (Logic) — `IConfigService.set_setting` / `YamlConfigAdapter.set_setting` (atomic, 2026-10-03)
- **Atomicity:** the `IConfigService.set_setting` abstract member and the `YamlConfigAdapter.set_setting` implementation landed as ONE green-to-green unit (Impact Audit). Declaring the member alone makes `YamlConfigAdapter` uninstantiable (`TypeError: Can't instantiate abstract class ... with abstract method set_setting`), which would red every adapter-constructing test (`test_yaml_config_adapter*.py`, `test_config_defaults.py`, `tests/harness/setup/real_adapter_mixin.py`). A census confirmed `YamlConfigAdapter` is the sole production implementer and every test double is an auto-specced mock, so no other class needed the member.
- **`set_setting` body (spike-verified, `probe_ku1`):** both mandatory fixes are implemented — (a) `os.makedirs(os.path.dirname(self._config_path), exist_ok=True)` runs BEFORE the write (guards the `root_dir`-based `.teddy/` parent case); (b) the in-memory merged `_config` cache is updated in place AFTER the disk write (a disk-only write left the cache stale). Dot-notation traversal, config-file + parent-directory creation, comment-stripping persistence (user file only; baseline never written), and preservation of unrelated keys all behave per spec §3.
- **Tests:** four unit tests added to `tests/suites/unit/adapters/outbound/test_yaml_config_adapter.py` — persistence + cache sync, file + parent-dir creation, dot-notation nesting, and unrelated-key preservation. No new `[DEBT]`.

### Deliverable #2 (Contract) — Baseline default editor `""` + commented `diff_flags` (2026-10-03)
- **Change (spec §1):** `src/teddy_executor/resources/config/config.yaml` baseline `editor` changed `"code"` → `""`, with a `# Fallback chain: Config -> VISUAL/EDITOR env vars -> discovery prompt.` comment and a new commented-out `diff_flags` block (`# Example: ["--diff", "--wait"]` / `# diff_flags: []`). Because the `diff_flags` section is intentionally commented out, its ABSENCE is the contract surface for this deliverable — the later `get_diff_viewer_command()` Logic deliverable reads it as unset until a user opts in.
- **Green-to-Green confirmed:** the `git grep` census showed the only baseline dependency on `"code"` was this file; every test hit (`test_console_tooling_editor.py`, `test_read_preview_opens_real_file.py`, etc.) passes `"code"` as a MOCKED config input rather than reading the baseline. No test or production consumer asserted the baseline editor default, so the change required no Migration sweep and the full suite stayed green.
- **Tests:** one baseline-default test added to `test_yaml_config_adapter.py` (`test_editor_default_is_empty_in_baseline`), reusing the `fs.add_real_file(resources.files(...))` + empty-user-config idiom from the adjacent `test_auto_pruning_defaults_are_present` to prevent a divergent fake-fs setup. No new `[DEBT]`.

### Plan Audit (2026-10-03) — Re-partition of the two leading Harness deliverables (#3, #4)
- **Finding (#3 — premature):** `Add KNOWN_EDITORS fixture and mock discover_editors patterns to test_console_tooling_editor.py` referenced members that DO NOT EXIST yet — a `git grep` over `src`/`tests` returned ZERO hits for `KNOWN_EDITORS` and `discover_editors` (they are introduced by the Seam deliverable and the Wiring deliverable, which are listed BELOW it). Writing fixtures/tests against undefined members would land RED tests without GREEN code, violating the green-to-green rule. Additionally, the existing `mock_env` fixture (`POSIXPathMock(spec=ISystemEnvironment)`) ALREADY supports `which()` mocking, so no standalone fixture infrastructure is required. → **Re-partitioned as SUPERSEDED:** the `KNOWN_EDITORS` assertion test ships with the Seam and the `discover_editors` behavioural tests ship with the Wiring.
- **Finding (#4 — no-op):** `Update IConfigService mock in test harness (mocking.py, composition.py) to implement set_setting()` is a verified NO-OP. The Impact Audit and the harness reads (`mocking.py`, `composition.py`) confirmed every `IConfigService` double is auto-specced and gains `set_setting` from the spec; no hand-rolled concrete fake exists. → **Marked verified NO-OP** (kept only as a guard).
- **Consequence:** with #3 and #4 resolved, the next true atomic unit is the `KNOWN_EDITORS` **Seam**. No new deliverables were added; no behavioural scope was lost.

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
- [ ] Console UI: the discovery block ALWAYS shows the `Editor Setup` header above a bracketed list (`[1] nvim` …) with no paths shown
- [ ] Console UI: entering an out-of-range number shows `'{raw}' is not a valid selection. Choose 1-{n}.` and re-prompts
- [ ] Console UI: entering an unavailable custom command shows `'{raw}' was not found in PATH.` and re-prompts; an available custom command is saved exactly as typed
- [ ] Console UI: empty input saves `"disabled"` and prints `Editor preference saved to .teddy/config.yaml.` (no "Edit it directly at any time.")
- [ ] Console UI: the nothing-found branch still shows the `Editor Setup` header above `No known editors found. Enter a custom editor command (leave empty to disable):`
