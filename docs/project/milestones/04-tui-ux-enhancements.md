# Milestone: TUI & UX Enhancements

- **Status:** In Progress
- **Depends On:** None
- **Specs:** [Interactive Session Workflow](/docs/project/specs/interactive-session-workflow.md), [Plan Format](/docs/project/specs/plan-format.md), [Plan Format Validation](/docs/project/specs/plan-format-validation.md)

## Motivation
Make the interactive reviewer truthful about the session it is showing: which model is answering, what it has cost, which files the next turn carries, and what each key does on every node. The same pass closes the protocol gaps an interactive workflow exposes — a rename or removal that leaves a context manifest pointing at a dead path, a report that orders actions by how they were written rather than how they ran, a rationale section that vanishes because the reviewer recognizes only four headings — and gives the unattended `execute` run the interrupt handling the session loop already has.

## Requirements
1. **Right Panel Metadata Visibility:** The Context root shows the effective model, its provider, and the cumulative session cost at exactly four decimal places, and every other cost display — the terminal telemetry line and the guardrail limit notice — renders the same figure through the same formatter.
2. **Context Interaction Enhancements:** `e` acts on context nodes — opening `session.context` or `turn.context` from the matching root, opening the file itself from a file row, and offering an agent switch from the System node.
3. **TUI Navigation Polishing:** Alt+Up/Down walks the Context subsections as well as Rationale and Action Plan, and stops at the boundaries by scrolling instead of wrapping.
4. **Layout Padding Consistency:** One inset governs the left pane, both right-pane variants, and every row, so no section starts at a different gutter.
5. **Tier 2 Editing:** A parameter whose value is multiline or longer than 100 characters opens in the external editor instead of the single-line modal.
6. **Rationale Heading Parsing:** The reviewer opens a node for every `###` heading a rationale carries, fence-aware, with a leading `Untitled` entry for preamble and a quieter `Untitled` node when the rationale carries no heading at all.
7. **Manual Execution Logging & Ordering:** Deselected, halted, and interrupted actions are reported through `notify_skipped_action`, and manually executed actions appear in real execution order in both the console log and `report.md`.
8. **MOVE and DELETE Actions:** `MOVE` and `DELETE` action types for files and directories, with live `turn.context` and `session.context` synchronization.
9. **Interrupt Mechanism:** The two-phase `q` / Ctrl+C bracket covers the stateless `execute` run as well as the session loop, through one shared lifecycle that keeps a single owner of the process-global SIGINT disposition.
10. **Waiting Indicator:** Animated braille spinner during model generation via `IUserInteractor.begin_waiting` / `end_waiting`.
11. **Guardrail Turn Budget (verified delivered — preserve):** measured as delivered, so the residual work was regression pins rather than production code: `--max-turns` and `--max-cost` exist on both `start` and `resume`, `should_continue` returns `(True, None)` under plan approval and when `guardrails.enabled` is false, and `_orchestrate_session_loop` seeds `initial_turn` at `0` on every run while seeding `initial_cost` from the session's persisted cost, so a resumed run's turn budget counts this run instead of being inflated by the turns already spent. The default stays 150 (product decision, 2026-11-26) and agrees across all four spellings — the schema, the bundled `config.yaml`, the guard's fallback, and its component page — with the bundled value and the resolution fallback pinned against the schema default by name.

## Constraints
- **The reviewer is a shared seam:** five slices edit `textual_plan_reviewer_helpers.py`, and three edit the reviewer app or widget module, so slices running in parallel MUST use separate workspaces and rebase before merge instead of editing one tree.
- **`ProjectContext` is the shared contract:** Requirements 1 and 2 both read reviewer metadata from `ProjectContext`, and the DTO extension lands in slice 04-05 first so the context actions consume the field set rather than deriving it a second time.
- **One cost formatter:** `format_cost_usd` is the only money renderer, at exactly four decimal places with `$???` for an unrecorded amount; the terminal telemetry line, the guardrail limit notice, and the panel row all call it, so the three cannot disagree again.
- **Provider derivation is unresolved:** whether Provider shows the prefix segment of the resolved model string or LiteLLM's own resolved provider stays a `[Domain]` unknown inside slice 04-05. If the resolved provider is required, `ProjectContext` gains a second field instead of the reviewer calling the LLM adapter at render time.
- **Padding is enforced by assertion, not by layout test:** Textual layout is not observable from the harness, so the inset is single-sourced in Python and asserted against the rendered stylesheet per selector.
- **MOVE/DELETE keep manifests truthful:** validation MUST fail when a `MOVE` destination already exists, and both actions MUST rewrite the live `turn.context` and `session.context`; archived session directories stay immutable. The parser MUST coerce `Recursive` to a boolean the way `CREATE` coerces `Overwrite`, so `Recursive: false` is falsy rather than a truthy non-empty string.
- **Alt+Up/Down ownership:** `RationaleDetail` and `ParameterDetail` keep their pane-local scroll bindings, and the tree-level Alt bindings stay authoritative for navigation only while the tree holds focus.
- **Interrupt lifecycle ownership:** the SIGINT disposition and the quit-key listener are process-global singletons, so their lifecycle is hoisted into one seam both boundaries use, because two owners taking their own `install()` snapshot would each restore the other's handler.
- **The waiting indicator is display-only:** the port opens and closes a region and the console adapter renders it, with nothing rendered when stderr is not a terminal, so logs, redirects, and CI transcripts stay newline-delimited.
- **Test harness strategy:**
  - **TUI changes:** drive navigation and interaction through `TuiDriver`, and verify manifest updates through `FileSystemObserver`.
  - **Config changes:** use `YamlConfigAdapter` contract tests for new keys.
  - **Action types:** extend `ActionFactory` and `PlanValidator` tests for both new types, including every rejection branch.
  - **Interrupt:** add an acceptance test proving an interrupted `execute` run writes an `INTERRUPTED` report and restores the previous SIGINT disposition.
- **Already delivered, explicitly out of scope:** configurable `context.max_depth` (schema, bundled config, and `LocalRepoTreeGenerator`); editor basename normalization, delivered by slice 04-01; and the `diff_flags` config override, already honoured by `ConsoleToolingHelper.get_diff_viewer_command`. The residual diff-routing divergence between the static flag table and that override is owned by [Milestone 6](/docs/project/milestones/06-cross-cutting-consolidation.md).
- **`--console` no longer exists, explicitly out of scope:** a repository-wide census finds no `--console` literal in `src/` or the specs, so both the deprecation this milestone used to carry and the removal it deferred are already complete. The stale removal bullet in [Milestone 5](/docs/project/milestones/05-quality-gate-debt-reconciliation.md) is reconciled there.

## Slices
- [x] [04-01-editor-basename-normalization](../slices/04-01-editor-basename-normalization.md): Normalizes editor basenames for Windows launcher suffixes so `codium.CMD` and `nvim.CMD` are detected. Delivered.
- [ ] [04-02-waiting-feedback](../slices/04-02-waiting-feedback.md): Tackles Req 10. `IUserInteractor` gains a waiting region and the console adapter renders a transient spinner, with no-op behaviour off a terminal.
- [ ] [04-03-interruptible-execute](../slices/04-03-interruptible-execute.md): Tackles Req 9. Hoists the install/restore and listener start/stop lifecycle into one seam, then brackets the stateless `execute` run with it.
- [x] [04-04-guardrail-defaults](../slices/04-04-guardrail-defaults.md): Tackles Req 11. Pins the yolo-only gate and the per-run resume baseline, corrects the turn seed that inflated a resumed run's budget, asserts the four 150 spellings agree, and records the behaviour as built. Delivered.
- [ ] [04-05-context-metadata](../slices/04-05-context-metadata.md): Tackles Req 1. `ProjectContext` gains the model name and session cost, and one `format_cost_usd` replaces the two other money formats.
- [ ] [04-06-context-actions](../slices/04-06-context-actions.md): Tackles Req 2. `e` on a context node resolves to a manifest, a file, or the agent roster, and a persona switch re-composes the agent+MRP prompt through the same seam `resume -a` uses.
- [ ] [04-07-section-navigation](../slices/04-07-section-navigation.md): Tackles Req 3. A derived section sequence replaces the three-root modulo, and boundaries scroll instead of wrapping.
- [x] [04-08-panel-insets](../slices/04-08-panel-insets.md): Tackles Req 4. One `PANEL_INSET` rendered into the stylesheet and asserted per selector. Delivered.
- [ ] [04-09-tier2-editing](../slices/04-09-tier2-editing.md): Tackles Req 5. One predicate routes long or multiline values through the external editor.
- [ ] [04-10-rationale-sections](../slices/04-10-rationale-sections.md): Tackles Req 6. A fence-aware split replaces the four-heading allowlist, and the fallback label becomes `Untitled`.
- [ ] [04-11-move-delete-actions](../slices/04-11-move-delete-actions.md): Tackles Req 8. Two protocol members across every registration site, with live manifest synchronization.
- [ ] [04-12-manual-execution-ordering](../slices/04-12-manual-execution-ordering.md): Tackles Req 7. An execution stamp plus the skip notices the dead port method was meant to emit.
