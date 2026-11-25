# Milestone: TUI & UX Enhancements

- **Status:** In Progress
- **Depends On:** None
- **Specs:** [docs/project/specs/interactive-session-workflow.md](/docs/project/specs/interactive-session-workflow.md)

## Goal
To provide a polished, intuitive interactive experience that gives users full visibility into session state and context, while adding foundational quality-of-life features like MOVE/DELETE actions and session interrupt.

## Requirements
1. **Configurable Tree Depth:** Configurable `context.max_depth` setting in config schema and tree generator.
2. **Interrupt Mechanism:** Graceful interrupt handling (`InterruptGuard`) for `q` and Ctrl+C, wired through a single shared lifecycle that covers both the stateful session loop (`start`/`resume`) and the stateless `execute` run, which lacks it today.
3. **Editor Basename Normalization:** Launcher-suffix stripping for Windows editor wrappers (`codium.CMD`, `nvim.CMD`) delivered by slice `04-01`.
4. **Editor Diff Mapping:** Translation table for diff flags with `diff_flags` config override.
5. **Waiting Indicator (04-02):** Animated braille spinner during model generation via `IUserInteractor.begin_waiting`/`end_waiting`.
6. **MOVE and DELETE Actions:** File and directory `MOVE` and `DELETE` action types with live context manifest synchronization.
7. **Manual Execution Logging & Ordering:** Re-emit skipped actions (`notify_skipped_action`) and record manually executed actions (`x`) in real execution sequence order.
8. **Rationale Heading Parsing:** Reviewer opens a node for every `###` heading in rationale, falling back to `Raw` if none present.
9. **TUI Navigation Polishing:** Alt+Up/Down section jumping with sub-section awareness and scroll-at-bottom behavior.
10. **Context Interaction Enhancements:** Context `e` key actions to open context manifests, files, or agent switch menu.
11. **Right Panel Metadata Visibility:** Display model name, provider, and session cost rounded to nearest cent when Context root is selected.
12. **Tier 2 Editing:** Automatically open external editor for parameters that are multiline or >100 characters.
13. **Layout Padding Consistency:** Consistent padding across left and right TUI panels.

## Constraints
- **Waiting Indicator:** The port only opens and closes a waiting region; the console adapter owns the rendering. Nothing is rendered when stderr is not a terminal, so logs, redirects, and CI transcripts stay newline-delimited.
- **Test Harness Strategy:**
    - **TUI Changes:** Use the existing TUI test driver (`TuiDriver`) for navigation and interaction tests. Use `FileSystemObserver` to verify context manifest updates for MOVE/DELETE.
    - **Config Changes:** Use `YamlConfigAdapter` contract tests for new config keys.
    - **Action Types:** Extend `ActionFactory` and `ActionValidator` tests for `MOVE` and `DELETE` validation rules.
    - **Interrupt:** Test via `ShellAdapter` signal handling or `ConsoleInteractor` ask-loop interaction, and add an acceptance test proving an interrupted `execute` run still writes an `INTERRUPTED` report and restores the previous SIGINT disposition.
- **Poka-Yoke:** MOVE/DELETE MUST update context manifest files automatically. Validation MUST fail if MOVE destination path already exists.
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
- **Waiting Indicator:** `IUserInteractor.begin_waiting(message)` and `end_waiting()` bracket the generation retry loop, so the region covers the model call and nothing else. `ConsoleInteractorAdapter` renders a transient `Rich` live region on its stderr console when `is_terminal`, showing a bare braille-dot spinner on one line beneath the telemetry with no label and no elapsed suffix, and both methods are no-ops otherwise. The contract is display-only: `end_waiting` never raises, tolerates being called without a matching `begin_waiting`, and the region stops on interpreter exit even when a quit abandons the worker that opened it. Two invariants bound the change: the indicator never rewrites a line it did not print, so the banner, telemetry, and plan summary stay byte-identical, and it never reads stdin, installs a signal handler, or blocks, so `q` and Ctrl+C keep landing within one 50 ms poll slice.
- **Interrupt Lifecycle Ownership:** The SIGINT disposition and the quit-key listener are process-global singletons whose install/restore and start/stop lifecycle is owned today by the session loop alone, as the `boundary_owns_interrupt_lifecycle` invariant in [the CLI adapter component page](/docs/architecture/adapters/inbound/cli.md) records, while the stateless `execute` command runs the orchestrator with no handler at all. Covering it therefore hoists that lifecycle into one seam both callers use, because two owners taking their own `install()` snapshot would each restore the other's handler. `execute` adopts the bracket the session loop already proves: install the handler and start the listener before `orchestrator.execute(...)`, then stop the listener and restore the previous disposition in a `finally` that also covers a `VALIDATION_FAILED` report, an action failure, and the `typer.Exit` those raise. The reviewer mounts inside `orchestrator.execute`, so the listener is already live during TUI review in sessions; the reviewer's own `q` binding stays authoritative there and the existing `stdin_owned()` claim is what keeps the raw reader off Textual's keys, so `execute` inherits that ordering instead of inventing a second one. A drain names the pressed key through `format_interrupt_notice(guard.source)` and still writes the report, so the run is recorded `INTERRUPTED`; a `KeyboardInterrupt` raised in the WAITING phase prints the same notice instead of escaping as a traceback. The `boundary_owns_interrupt_lifecycle` invariant flips from session-only to both boundaries in the same commit as the code.

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
> 10. Interrupt mechanism, shared by the session loop and the stateless `execute` run
> 11. `--console` deprecation marking
> 12. Manual execution logging and ordering
> 13. Rationale heading parsing (generalize beyond the four canonical sections)

**Scheduled Slices:**
- [ ] [04-02-waiting-feedback](/docs/project/slices/04-02-waiting-feedback.md): Tackles the waiting-feedback requirement. Animated indicator for the duration of the model call, port extension plus stderr rendering.
- [ ] 04-03-interruptible-execute (slice document to be authored by the Architect): Tackles the interrupt requirement for the stateless path. Hoists the install/restore and listener start/stop lifecycle into one seam shared with the session loop, then brackets `execute` with it so `q` and Ctrl+C drain gracefully, the report still lands as `INTERRUPTED`, and the previous SIGINT disposition is restored on every exit path.

**Delivered Slices:**
- [x] [04-01: Normalize Editor Basenames for Windows Launcher Suffixes](/docs/project/slices/04-01-editor-basename-normalization.md)
