# Milestone: TUI & UX Enhancements

- **Status:** In Progress
- **Specs:** [docs/project/specs/interactive-session-workflow.md](/docs/project/specs/interactive-session-workflow.md)

## Goal
To provide a polished, intuitive interactive experience that gives users full visibility into session state and context, while adding foundational quality-of-life features like MOVE/DELETE actions and session interrupt.

## Solution
Expand the TUI with improved navigation, context interactions, and metadata visibility. Add new action types (`MOVE`, `DELETE`) with context manifest awareness. Implement a session interrupt mechanism. Deprecate `--console` mode.

## Guidelines
- **Test Harness Strategy:**
    - **TUI Changes:** Use the existing TUI test driver (`TuiDriver`) for navigation and interaction tests. Use `FileSystemObserver` to verify context manifest updates for MOVE/DELETE.
    - **Config Changes:** Use `YamlConfigAdapter` contract tests for new config keys.
    - **Action Types:** Extend `ActionFactory` and `ActionValidator` tests for `MOVE` and `DELETE` validation rules.
    - **Session Interrupt:** Test via `ShellAdapter` signal handling or `ConsoleInteractor` ask-loop interaction.
- **Poka-Yoke:** MOVE/DELETE MUST update context manifest files automatically. Validation MUST fail if MOVE destination path already exists.

## Technical Specifications
- **MOVE Action:** Takes `Source` and `Destination` paths. Validates source exists and destination does not, and creates missing destination parents. Rewrites the live `turn.context` and `session.context` so the old path becomes the new one; archived session directories stay immutable. Supports files and directories, where renaming is a `MOVE` within the same parent. Contract: [plan-format.md](/docs/project/specs/plan-format.md) and [plan-format-validation.md](/docs/project/specs/plan-format-validation.md).
- **DELETE Action:** Takes `Path` plus an optional `Recursive` flag, required for a directory that is not empty. Validates path exists. Removes the path, and for a directory every entry beneath its prefix, from the live `turn.context` and `session.context`; archived session directories stay immutable. Supports files and directories. The parser must coerce `Recursive` to a boolean the way `CREATE` coerces `Overwrite`, so `Recursive: false` is falsy rather than a truthy non-empty string.
- **TUI Changes:**
    - Alt+Up/Down: Section navigation with scroll-at-bottom behavior and sub-section awareness.
    - `e` key: Context-sensitive actions (open context file, open file, agent switch).
    - Right panel metadata: Model name + provider + session cost (rounded to nearest cent).
    - Consistent padding across both panels.
    - Editor detection: Long/multiline params open in external editor.
- **Deprecation:** `--console` flag marked deprecated. No functional removal in this milestone (deferred to M5).
- **Manual Execution Logging & Ordering:** On plan submit, skipped actions (deselected, halted, interrupted) should be re-emitted to the console via the existing `notify_skipped_action` formatter. Manually executed actions (`x`) must appear in actual execution order in both the console log and `report.md`, not original plan order. This requires a per-action execution sequence stamped when each action runs.
- **Rationale Heading Parsing:** The plan reviewer opens a node for every `###` heading a rationale carries and labels it with the heading text, so a plan that adds, renames, or reorders a section is shown as authored instead of having that section folded into its predecessor. The four canonical sections stay the authored contract in [plan-format.md](/docs/project/specs/plan-format.md); only the reviewer's parser restriction is removed. The split must be fence-aware, because a `###` line inside a fenced block currently merges into its predecessor and an unguarded split would tear the fence apart. Text before the first heading renders as a leading `Raw` entry rather than being dropped, and a rationale with no heading at all still renders as one quieter `Raw` node so archived plans and resumed sessions stay reviewable. `ALLOWED_RATIONALE_SECTIONS`, `recognized_rationale_sections`, and `rationale_entries` collapse into a single `rationale_sections` entry point; `test_tui_only_accepts_markdown_headings` and `test_recognized_rationale_sections_merge_unrecognized_headings` pin the behaviour this removes and must be replaced rather than relaxed; and the `rationale_heading_only` invariant in [the reviewer component page](/docs/architecture/adapters/inbound/textual_plan_reviewer.md) flips in the same commit as the code.

## Slices
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
> 9. Configurable tree depth
> 10. Session interrupt mechanism
> 11. `--console` deprecation marking
> 12. Manual execution logging and ordering
> 13. Rationale heading parsing (generalize beyond the four canonical sections)

**Delivered Slices:**
- [x] [04-01: Normalize Editor Basenames for Windows Launcher Suffixes](/docs/project/slices/04-01-editor-basename-normalization.md)
