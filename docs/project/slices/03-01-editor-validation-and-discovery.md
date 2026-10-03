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
- [x] **Seam** — Add `KNOWN_EDITORS: list[str]` class-level constant to `ConsoleToolingHelper` (as specified in spec 2a)
- [x] **Wiring** — Add `discover_editors() -> list[tuple[str, str]]` method to `ConsoleToolingHelper` with PATH scanning and deduplication
- [x] **Wiring** — Modify `find_editor()` to handle "disabled" sentinel (returns None immediately, bypasses env fallback)
- [x] **Wiring** — Extend `_DIFF_FLAGS` translation table with all entries from spec 2d (add idea, webstorm, phpstorm, pycharm, rubymine, goland, clion, fleet)
- [x] **Logic** — Implement `YamlConfigAdapter.set_setting()` with dot-notation support, file creation, cache update, and YAML persistence
- [x] **Logic** — Implement `get_diff_viewer_command()` unknown editor fallback: return `[editor_path]` with no flags when editor not in `_DIFF_FLAGS`
- [x] **Logic** — Implement `get_diff_viewer_command()` `diff_flags` config override: use config value instead of `_DIFF_FLAGS` when `diff_flags` key is set
- [x] **Migration** — Add `_prompt_for_editor_selection()` and `_prompt_for_custom_editor()` prompting functions with `typer.prompt()` input validation (re-sequenced BEFORE `_validate_editor_config` — the orchestrator calls these; see the Plan Audit note in Implementation Notes)
- [x] **Migration** — Add `_validate_editor_config(container)` function to `session_cli_handlers.py` with discovery and prompting flow (calls the two prompting helpers above)
- [x] **Harness** — Make the default test harness editor-safe: configure the harness `IConfigService` mock (`test_environment.py` `_apply_config_defaults`) so `get_setting("editor")` resolves the `"disabled"` sentinel by default, making preflight editor validation inert for CLI-driving tests. Tests that exercise editor behaviour override it explicitly via `_configure_editor` (the harness-sanctioned `get_setting.side_effect` override). *(PREPENDED by Systemic Recovery — see Implementation Notes. Prerequisite for the merged preflight deliverable below: without it, the editor gate prompts every interactive CLI test and the suite reds at 15 failures.)*
- [ ] **Migration** — ⚠ MERGED (was #13 + #14): add `interactive: bool = True` to `_run_cli_preflight_check()` AND thread it from ALL THREE production callers — `handle_new_session` (line 447), `handle_plan_generation` (line 715), `handle_resume_session` (line 836) — calling `_validate_editor_config(container)` only when interactive. The signature change and every caller update MUST land as ONE atomic green-to-green unit (the default-ON gate is NOT green-to-green on its own — the callers do not forward the flag at HEAD). `handle_new_session`/`handle_resume_session` forward their existing `interactive`; `handle_plan_generation` passes `interactive=False` (a one-shot, non-session command that must not block on an editor prompt).
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

### Deliverable #5 (Seam) — `KNOWN_EDITORS` curated discovery list (2026-10-03)
- **Change (spec §2a):** added `KNOWN_EDITORS: list[str]` as a class-level constant on `ConsoleToolingHelper` in `console_tooling.py`, above the `_DIFF_FLAGS` table. The list is the curated set of terminal + GUI/IDE editor executable names scanned by the (next) `discover_editors()` Wiring deliverable.
- **Green-to-Green confirmed:** the constant is purely additive — no existing production consumer reads it yet (only the forthcoming `discover_editors()` will), so the full suite stayed green with no Migration sweep.
- **Tests:** one Seam contract test added to `tests/suites/unit/adapters/outbound/test_console_tooling_editor.py` (`test_known_editors_lists_the_curated_editor_set`) — asserts the member is a list of unique strings equal to spec §2a's curated set, pinning the exact contract. This is a contract test on pure data (not re-implemented logic). No new `[DEBT]`.

### Deliverable #6 (Wiring) — `discover_editors()` PATH scanning (2026-10-03)
- **Change (spec §2a):** added `ConsoleToolingHelper.discover_editors() -> list[tuple[str, str]]` in `console_tooling.py` (placed after `__init__`). It iterates `KNOWN_EDITORS` in order, resolves each name via `ISystemEnvironment.which()`, and returns `(basename, resolved_path)` pairs — deduplicated by resolved path (the same binary reachable under two aliases is reported once, under its first `KNOWN_EDITORS` name) and ordered by the `KNOWN_EDITORS` list.
- **Green-to-Green confirmed:** the method is purely additive — no production consumer calls it yet (the preflight `_validate_editor_config` flow that consumes it is a later Migration deliverable), so the full suite stayed green with no Migration sweep.
- **Test-layer note:** the superseded Harness #3 intent was folded here (Plan Audit): the three behavioural tests for `discover_editors()` ship with this Wiring bundle, co-located in the existing `tests/suites/unit/adapters/outbound/test_console_tooling_editor.py` where `ConsoleToolingHelper` and the `mock_env` fixture already live. The `mock_env` (`POSIXPathMock(spec=ISystemEnvironment)`) already supports `which()` side-effects, so no standalone fixture was needed.
- **Tests:** three unit tests added — ordered discovery of a found subset, dedup-by-resolved-path (first alias wins), and empty-list-when-none-found. No new `[DEBT]`.

### Deliverable #7 (Wiring) — `find_editor()` "disabled" sentinel (2026-10-03)
- **Change (spec §2b):** `find_editor()` now reads `get_setting("editor")` once into `editor_str` and, before any resolution, returns `None` when `editor_str.strip().lower() == "disabled"`. This bypasses the `VISUAL`/`EDITOR` env fallback entirely (an explicit user disablement), and is case- and whitespace-insensitive.
- **Test-layer note:** although the slice labels this deliverable `Wiring`, it is a discrete core-logic rule on an adapter; per the spec's Test Strategy it is unit-tested in the existing `tests/suites/unit/adapters/outbound/test_console_tooling_editor.py` alongside the five sibling `find_editor()` tests (no acceptance boundary exercises `find_editor()` end-to-end until the later preflight Migration deliverable).
- **Green-to-Green confirmed:** the guard is additive — none of the five pre-existing `find_editor()` tests pass `"disabled"` as the config, so their behaviour is unchanged; the full suite stayed green with no Migration sweep.
- **Tests:** one parametrized test added (`test_find_editor_returns_none_for_disabled_sentinel`) covering `"disabled"`, `"DISABLED"`, and `"  Disabled  "`, asserting both `result is None` and that `get_env` is NEVER called (pinning the env-bypass). No new `[DEBT]`.

### Deliverable #8 (Wiring) — `_DIFF_FLAGS` JetBrains-family expansion (2026-10-03)
- **Change (spec §2d):** extended the class-level `_DIFF_FLAGS` translation table on `ConsoleToolingHelper` with the eight JetBrains-family editors — `idea.sh`, `webstorm`, `phpstorm`, `pycharm`, `rubymine`, `goland`, `clion`, `fleet` — each mapped to the bare `["diff"]` subcommand token. The pre-existing entries (`vim`/`vi`/`nvim` `["-d"]`, `code`/`cursor`/`codium`/`zed` `["--diff"]`, `idea` `["diff"]`) are unchanged.
- **Green-to-Green confirmed:** the table extension is purely additive — adding dict keys cannot change any existing lookup result, so no Migration sweep was needed and the full suite stayed green.
- **Spike-backed convention:** the bare `"diff"` token (no dash) is mechanically sound — `probe_ku2` observed the launcher argv `["diff", <file1>, <file2>]` through `subprocess.run` for the live `idea` entry and for all eight simulated JetBrains additions (see Prototype Findings, KU2).
- **Tests:** one parametrized unit test added to `tests/suites/unit/adapters/outbound/test_console_tooling_editor.py` (`test_diff_flags_translation_table_includes_jetbrains_editors`) asserting each new key maps to `["diff"]`. No new `[DEBT]`.

### Deliverable #9 (Logic) — `get_diff_viewer_command()` unknown-editor fallback (2026-10-03)
- **Change (spec §2c):** the method's editor-resolution tail was replaced with the canonical `self.find_editor()` call (removing the inline duplicate of `get_setting("editor")` + `VISUAL`/`EDITOR` + `which`). On a translation-table miss (basename absent from `_DIFF_FLAGS`), it now returns `editor_cmd[:1]` — the resolved editor path with no flags — instead of `None`, so the caller passes both file paths as separate arguments and the editor opens them in separate tabs.
- **Side effect (free consequence, no separate deliverable):** because the tail now routes through `find_editor()`, `get_diff_viewer_command()` also honours the "disabled" sentinel (returns `None` when disabled) and the `VISUAL`/`EDITOR` env fallback — matching spec §5's "consumers of find_editor() handle None gracefully".
- **Not in scope (kept atomic):** the `diff_flags` config override (spec §2c step 0) is NOT added here; it is the next Logic deliverable (#10).
- **Green-to-Green confirmed:** the only observable behaviour change is the intended fallback. The `TEDDY_DIFF_TOOL` branch is untouched; known editors (`vim`/`nvim`/`code`/`cursor`/`zed`/`idea`) keep returning `[path] + flags`; a resolved-but-unknown editor now returns `[path]`; an unresolved editor still returns `None`.
- **Tests:** the existing `test_diff_viewer_returns_none_for_unknown_editor` was repurposed (Migration) into `test_diff_viewer_returns_editor_path_for_unknown_editor`, repinning the contract to `["/usr/bin/nano"]` rather than adding a duplicate. No new `[DEBT]`.

### Deliverable #10 (Logic) — `get_diff_viewer_command()` `diff_flags` config override (2026-10-03)
- **Change (spec §2c step 0):** inserted a `diff_flags` block at the TOP of `get_diff_viewer_command()`, ahead of the `TEDDY_DIFF_TOOL` check. When `config_service.get_setting("diff_flags")` is a truthy LIST, the method returns `find_editor()[:1] + diff_flags` — the resolved editor path (flags stripped) prefixed to the configured flags — instead of the `_DIFF_FLAGS` translation-table value.
- **Priority (spec §2c):** `diff_flags` config override > `TEDDY_DIFF_TOOL` env var > `_DIFF_FLAGS` translation table > unknown-editor fallback. This matches the design doc's priority-chain listing; the design doc's "Failure Modes" line claiming "`TEDDY_DIFF_TOOL` takes precedence over all" is STALE and must be corrected in the slice's final As-Built Update.
- **Crash guard (spec failure mode):** the block is guarded by `isinstance(diff_flags, list)`, so a malformed non-list value (e.g. a bare string) is skipped and the method falls through to the translation table — pinning the documented "skip the override on malformed config" behaviour.
- **Green-to-Green confirmed:** the block is additive and guarded — every pre-existing test configures `get_setting.return_value` to a non-list string or `None`, so `isinstance(diff_flags, list)` is False, the block is skipped, and prior behaviour is unchanged; the full suite stayed green with no Migration sweep.
- **Tests:** three unit tests added to `TestGetDiffViewerCommand` — override-used-instead-of-table (nvim + `["--diff","--wait"]` → `["/usr/bin/nvim","--diff","--wait"]`), non-list-falls-through (string `"--diff"` → table flags `["/usr/bin/nvim","-d"]`), and override-outranks-`TEDDY_DIFF_TOOL`. No new `[DEBT]`.

### Plan Audit (2026-10-03) — Re-sequence of the editor-validation flow deliverables (#11, #12)
- **Finding (dependency inversion):** the slice listed `_validate_editor_config(container)` (#11) BEFORE the prompting helpers (#12), but #11 CALLS `_prompt_for_editor_selection()` / `_prompt_for_custom_editor()` (spec §4). Implementing #11 first would leave it referencing not-yet-existent helpers on its discovery path, so its behavioural test could not go green without either the helpers existing or a forbidden runtime patch. → **Re-sequenced:** the two prompting helpers now land FIRST as an independently testable, purely additive unit; `_validate_editor_config` follows and wires them together. No behavioural scope was lost.
- **Additive boundary confirmed:** both #11 and #12 are net-new module-level functions in `session_cli_handlers.py` with NO production caller yet — their only caller is `_run_cli_preflight_check()` (#13). Both are therefore Green-to-Green with no Migration sweep.
- **Forward green-to-green note (for #13):** wiring `_validate_editor_config()` into `_run_cli_preflight_check()` (default `interactive=True`) is the FIRST deliverable in this flow that touches a function EXERCISED by existing tests. `tests/suites/unit/adapters/inbound/test_session_preflight_wiring.py` has seven tests; six raise on LLM/agent errors before editor logic, and only `test_preflight_check_no_error_when_agent_exists` proceeds past that gate. The `env` harness resolves `IConfigService` / `ISystemEnvironment` as auto-specced mocks (`register_mock` → `POSIXPathMock(spec=port)`), so a bare `get_setting("editor")` returns a child `MagicMock` rather than a string. #13 MUST pin the editor-validation call site's behaviour for that existing test (e.g., pass `interactive=False` there, or configure the editor mock) so the additive editor gate does not perturb it — a Local Flaw resolution (editing the existing test), NOT a patch to external components.

### Deliverable #12 (Migration) — `_prompt_for_editor_selection()` / `_prompt_for_custom_editor()` (2026-10-03)
- **Change (spec §4):** added two net-new module-level prompting helpers in `session_cli_handlers.py` — `_prompt_for_editor_selection(config_service, helper, available)` (editors-found branch) and `_prompt_for_custom_editor(config_service, helper)` (nothing-found branch) — plus a shared `_persist_editor_choice()` that writes via `config_service.set_setting("editor", value)` and prints the green `Editor preference saved to .teddy/config.yaml.` confirmation. Both render the always-present cyan/bold `Editor Setup` header and emit entirely on **stderr**.
- **Selection behaviour:** a valid in-range number persists the selected editor's RESOLVED ABSOLUTE PATH; an out-of-range number prints the red `'{raw}' is not a valid selection. Choose 1-{n}.` and re-prompts; a custom command is validated via `helper._resolve_editor_cmd()` (`which()` on the first token) and persisted EXACTLY AS TYPED (flags preserved, e.g. `code --wait`) when available, else the red `'{raw}' was not found in PATH.` then re-prompt — a custom command is never accepted without passing `which()`. Empty input persists `"disabled"`; `EOFError`/`typer.Abort` (EOF/closed input) also persist `"disabled"`.
- **Custom-only behaviour:** when `discover_editors()` finds nothing, the header still renders above the single prompt `No known editors found. Enter a custom editor command (leave empty to disable):` with the same `which()`-validation loop.
- **Header ownership decision:** the spec's authoritative `_validate_editor_config` code block emits the branch warning (missing vs unconfigured) from config state the prompt functions do not hold, so the WARNING stays in #11; the always-present `Editor Setup` HEADER is rendered by the two prompt functions (per the spec's descriptive render order) so it appears on BOTH branches. Resulting render order: warning (#11) → blank → header → blank → list → blank → prompt.
- **Custom-command validation reuse:** validation delegates to `ConsoleToolingHelper._resolve_editor_cmd()` (the helper's own resolution) rather than reimplementing `shlex.split` + `which()` in the handler, avoiding Shadow Logic. `ConsoleToolingHelper` is now imported at module scope (a top-level import; no circular-import risk — `console_tooling` imports only core ports) so the prompt functions can type-annotate their `helper` parameter.
- **Green-to-Green confirmed:** both functions are net-new with no production caller yet (their only caller is `_run_cli_preflight_check`, deliverable #13) — purely additive, so the full suite stayed green with no Migration sweep.
- **Tests:** seven unit tests added to `tests/suites/unit/adapters/inbound/test_session_preflight_wiring.py` covering: number→resolved path, custom→typed, empty→disabled, out-of-range re-prompt, unavailable-custom re-prompt, custom-only valid→typed, and custom-only empty→disabled. `typer.prompt` is driven via the codebase's sanctioned `monkeypatch.setattr("typer.prompt", ...)` idiom; the `ConsoleToolingHelper` is built on auto-specced `POSIXPathMock` env/config doubles. No new `[DEBT]`.

### Deliverable #11 (Migration) — `_validate_editor_config(container)` orchestrator (2026-10-03)
- **Change (spec §4):** added `_validate_editor_config(container)` to `session_cli_handlers.py`, placed immediately after `_prompt_for_custom_editor` (adjacent to its two callees). It resolves `IConfigService` + `ISystemEnvironment` from the container, builds a `ConsoleToolingHelper`, reads `get_setting("editor")`, and branches: **disabled** → early return (no PATH scan, no prompt); **configured + found** → early return; **configured-but-missing** → yellow `⚠ Configured editor '{editor}' not found in PATH. Discovering alternatives...` then discovery; **unconfigured** (`""`/`None`) → yellow `No editor configured. Scanning for available editors in PATH...` then discovery. Discovery routes to `_prompt_for_editor_selection()` when editors are found, else `_prompt_for_custom_editor()`.
- **Spec deviation (deliberate):** the spec §4 code block imports `YamlConfigAdapter` but never uses it — that DEAD import was OMITTED. `IConfigService` and `ConsoleToolingHelper` are already imported at module scope (lines 19 and 28), so the ONLY function-local import added is `ISystemEnvironment`.
- **Ownership boundary:** the always-present `Editor Setup` header remains owned by the two #12 prompt helpers (rendered on BOTH branches); this orchestrator owns only the two branch WARNINGS. Resulting render order: warning → blank → header → blank → list → blank → prompt, all on stderr.
- **Green-to-Green confirmed:** the function is net-new with NO production caller yet (its only caller is `_run_cli_preflight_check`, deliverable #13) — purely additive, so the full suite stayed green with no Migration sweep.
- **Local Flaw (test setup, resolved):** the five orchestrator tests initially used `mock_config.get_setting.return_value = <X>`, which is INERT because `TestEnvironment._apply_config_defaults` installs `get_setting.side_effect = lambda k, default=None: default` (a callable side_effect takes precedence over `return_value`), so every test took the UNCONFIGURED branch. A shared `_configure_editor(mock_config, value)` helper now overrides the side_effect — the harness-sanctioned idiom (mirrored from `test_session_pruning_status_anchoring.py:13` etc.). This also repaired `test_..._when_configured_editor_missing`, which had been passing COINCIDENTALLY via the unconfigured branch (same `set_setting` assertion), so it now genuinely exercises the configured-missing branch.
- **Tests:** five unit tests added to `tests/suites/unit/adapters/inbound/test_session_preflight_wiring.py` — disabled-sentinel early return (asserts `which` and `set_setting` are NOT called), configured-editor-found early return (`set_setting` not called), unconfigured→discovery→persist, configured-missing→discovery→persist, and nothing-found→custom→`"disabled"`. `typer.prompt` is driven via the sanctioned `monkeypatch.setattr("typer.prompt", ...)` idiom. No new `[DEBT]`.

### Systemic Recovery (2026-10-03) — Re-partition of the preflight editor gate (#13 + #14) + a prepended Harness prerequisite
- **What happened:** the `_run_cli_preflight_check(interactive=True)` deliverable (#13) implemented its Red+Green (target suite 21 passed) but its Integration gate red the FULL suite at **15 failed / 1520 passed**. Diagnosis: the gate defaulted ON while the three production callers (447/715/836) still invoked `_run_cli_preflight_check` WITHOUT `interactive`, so editor validation ran on EVERY preflight — including sessions explicitly requested non-interactive. Two failure mechanisms surfaced: (A) the editor prompt firing under captured stdin (`OSError: reading from stdin while output is captured` / `SystemExit(1)`) and (B) `punq.MissingDependencyError: Failed to resolve ISystemEnvironment` in bare-`Container()` unit tests.
- **Classification (Phase 3, empirical rule):** a SYSTEMIC REGRESSION — fixing the suite requires modifying production code OUTSIDE #13's exact scope (the callers), so #13 is NOT green-to-green on its own. The slice's split of the gate (#13) from the caller wiring (#14) was wrong.
- **Recovery:** (1) **Abort** — `git reset --hard HEAD && git clean -fd` wiped #13's uncommitted edits and its diagnostic log (HEAD `9e3b7048`, clean tree). (2) **Re-partition** (this entry) — merge #13+#14 into ONE atomic deliverable AND prepend a Harness prerequisite.
- **Why a Harness prerequisite:** the editor gate is net-new INTERACTIVE behaviour at session startup. Every CLI test that drives an interactive `start`/`resume` runs against the harness `IConfigService` mock, whose `get_setting` returns the caller default → `editor == ""` → unconfigured → the discovery prompt. Making the harness default resolve the `"disabled"` sentinel makes preflight editor validation inert for tests by default; tests that exercise editor behaviour already override `get_setting` explicitly via `_configure_editor`. Without this, the merged deliverable cannot be green-to-green (≈15 interactive tests would each need bespoke editor input).
- **Corrected forward note:** the earlier "Forward green-to-green note (for #13)" predicting exactly ONE perturbed test is WRONG — the real blast radius was 15 tests across `test_session_replan_loop` (×2), `test_session_start_resequencing` (×2), `test_session_management` (×2), `test_session_resume_robustness` (×5), `test_streamlined_init`, `test_planning_visibility`, `test_pipeline_message_and_resume_flow`, and `test_session_orchestration_integration`. The merged deliverable + the Harness prerequisite supersede that prediction.
- **Next:** VCP this re-partitioned slice (dedicated Version Control turn), then RESTART Phase 1 for the prepended Harness deliverable.

### Harness (PREPENDED) — Editor-safe default test harness (2026-10-03)
- **Change:** `TestEnvironment._apply_config_defaults` now installs a `get_setting.side_effect` that returns the `"disabled"` sentinel for the `editor` key and the caller-supplied `default` for every other key (replacing the previous `lambda k, default=None: default`). This makes preflight editor validation inert for CLI-driving tests while preserving ordinary default-mirroring behaviour for all other keys.
- **Rationale (prerequisite for the merged preflight deliverable):** the editor gate is net-new INTERACTIVE behaviour at session startup; every CLI test that drives an interactive `start`/`resume` runs against the harness `IConfigService` mock. Making the default `editor` resolve the sentinel means those tests never reach the discovery prompt, so the merged deliverable can be green-to-green. Tests that exercise editor behaviour override `get_setting` explicitly via the harness-sanctioned `_configure_editor` side_effect helper.
- **Blast radius (verified during Orientation):** the standalone `mock_config` fixture in `mocks.py` installs its OWN `get_setting.side_effect`, and `test_console_tooling_editor.py` builds its own `POSIXPathMock(spec=IConfigService)` — both are immune. `test_session_preflight_wiring.py` overrides via `_configure_editor` — immune. Both the new `"disabled"` default and the prior unconfigured path resolve to `find_editor() -> None` (the env mock returns `None`), so no existing harness test regressed.
- **Tests:** one unit test added to `tests/suites/unit/test_environment_harness_config_mock.py` (`test_harness_config_mock_returns_disabled_for_editor`) pinning `editor -> "disabled"` and that other keys still mirror the caller default; the sibling `ui_mode` test remains green. Full-suite Integration gate: `1534 passed, 5 skipped`.
- **[DEBT]:** the `"disabled"` sentinel string literal is now duplicated across `console_tooling.py`, `session_cli_handlers.py`, and the harness `test_environment.py` — a shared-constant candidate (multi-file; deferred). Harvested to PROJECT.md.

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
