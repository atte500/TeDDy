# Milestone 4: TUI & UX Enhancements

- **Status:** Planned
- **Specs:** [docs/project/specs/interactive-session-workflow.md](/docs/project/specs/interactive-session-workflow.md)

## Goal (The "Why")
To provide a polished, intuitive interactive experience that gives users full visibility into session state and context, while adding foundational quality-of-life features like MOVE/DELETE actions, configurable limits, and session interrupt.

## Proposed Solution (The "What")
Expand the TUI with improved navigation, context interactions, and metadata visibility. Add new action types (`MOVE`, `DELETE`) with context manifest awareness. Introduce configurable session limits and tree depth settings. Implement a session interrupt mechanism. Make `--yolo` mode configurable by default. Deprecate `--console` mode.

## Guidelines (The "How")
- **Test Harness Strategy:**
    - **TUI Changes:** Use the existing TUI test driver (`TuiDriver`) for navigation and interaction tests. Use `FileSystemObserver` to verify context manifest updates for MOVE/DELETE.
    - **Config Changes:** Use `YamlConfigAdapter` contract tests for new config keys.
    - **Action Types:** Extend `ActionFactory` and `ActionValidator` tests for `MOVE` and `DELETE` validation rules.
    - **Session Interrupt:** Test via `ShellAdapter` signal handling or `ConsoleInteractor` ask-loop interaction.
- **Poka-Yoke:** MOVE/DELETE MUST update context manifest files automatically. Validation MUST fail if MOVE destination path already exists.

## Technical Specifications
- **MOVE Action:** Takes `source` and `destination` paths. Validates source exists and destination does not. Updates context manifest: renames path references in `.context` files to reflect the new location. Supports files and directories (renaming).
- **DELETE Action:** Takes a `path`. Validates path exists. Updates context manifest: removes path references from `.context` files. Supports files and directories.
- **Config Changes:**
    - `session.max_turns: 99` (default)
    - `session.max_cost: 5.0` (default, in dollars)
    - `context.max_tree_depth: 4` (default, 0 = unlimited)
    - `session.yolo_default: false` (default)
- **TUI Changes:**
    - Alt+Up/Down: Section navigation with scroll-at-bottom behavior and sub-section awareness.
    - `e` key: Context-sensitive actions (open context file, open file, agent switch).
    - Right panel metadata: Model name + provider + session cost (rounded to nearest cent).
    - Consistent padding across both panels.
    - Editor detection: Long/multiline params open in external editor.
- **Deprecation:** `--console` flag marked deprecated. No functional removal in this milestone (deferred to M5).

## Vertical Slices
> Slice definitions will be created by the Architect during the Design phase. The following high-level breakdown is anticipated:
>
> 1. TUI navigation improvements (Alt+Up/Down, section jumping)
> 2. Context interaction enhancements (`e` key actions)
> 3. Metadata visibility (model, cost in right panel)
> 4. Tier 2 editing (multiline/long param editor)
> 5. Editor & diff mapping cleanup
> 6. Layout padding consistency
> 7. MOVE action implementation
> 8. DELETE action implementation
> 9. Configurable session limits (max-turns, max-cost)
> 10. Configurable tree depth
> 11. Session interrupt mechanism
> 12. `--yolo` default config option
> 13. `--console` deprecation marking
> 14. Ad-hoc: CLI arg normalization (00-03)
> 15. Ad-hoc: Remove bare except in InitService (00-04)
