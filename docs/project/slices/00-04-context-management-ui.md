# Slice: Context Management UI
- **Status:** Planned
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Specs:** [context-management-ui.md](../specs/context-management-ui.md)
- **Prototype:** [link]
- **Showcase:** [link]
- **Component Docs:**
  - [ProjectContext](../../architecture/core/domain/project_context.md)
  - [ILlmClient](../../architecture/core/ports/outbound/llm_client.md)
  - [IConfigService](../../architecture/core/ports/outbound/config_service.md)

## Business Goal
Provide users with direct, UI-driven control over their session context with token visibility, and automate the removal of heavy or useless files to save tokens.

## Scenarios
> As a user running an interactive session, I want to see the token size and git status of my context files in the UI, so that I can make informed decisions about my token footprint.
```gherkin
Given an interactive session is running
When the plan review TUI is launched
Then there is a "Session Context" node in the action tree
And clicking it shows lists of context files separated by session and turn scopes
And each file displays its token count and git status
```

> As a user, I want the system to automatically deselect useless context files (like failed plans/reports or huge files) so I don't waste tokens without noticing.
```gherkin
Given auto-pruning is enabled in the configuration
And the current turn context contains a failed execution report
When the plan review TUI is launched
Then the failed execution report is shown in the context list but its checkbox is unchecked
And files in the session context are never unchecked automatically
```

## Deliverables
- [ ] **Contract** - Add `count_tokens` to `ILlmClient` and implement in `LiteLLMAdapter`.
- [ ] **Contract** - Create `ContextItem` DTO; update `ProjectContext` to hold a list of them.
- [ ] **Contract** - Add `auto_pruning` section (with granular toggles: `enabled`, `threshold_tokens`, `prune_failed_plans`, `prune_failed_reports`) to `ConfigService` and `config.yaml` defaults.
- [ ] **Contract** - Update `IPlanReviewer.review()` and `ExecutionOrchestrator.execute()` signatures to accept `project_context: Optional[ProjectContext]`.
- [ ] **Logic** - Update `ContextService` to parse git status strings, count tokens via `ILlmClient`, and build `ContextItem` lists.
- [ ] **Logic** - Implement auto-pruning heuristics in `SessionOrchestrator` (thresholds, failure artifacts detection, scope restrictions).
- [ ] **Wiring** - Pass `ProjectContext` from `SessionOrchestrator` -> `ExecutionOrchestrator` -> `TextualPlanReviewer`.
- [ ] **UI** - Create `ContextManagementView` widget in TUI (separate DataTables for session/turn, checkboxes, formatted columns).
- [ ] **UI** - Bind `ContextManagementView` to an `ActionTree` "Session Context" node.
- [ ] **Integration** - Update `ReviewerApp` to collect unchecked paths and set `plan.metadata["pruned_context"]`.
- [ ] **Integration** - Update `SessionOrchestrator` post-execution loop to read `pruned_context` and actively remove those files from the `turn.context` file and internal state.

## Delta Analysis
- **Domain/Ports:** `ProjectContext` expands. `ILlmClient` and `IPlanReviewer` get new signature capabilities.
- **Core Services:** `ContextService` gains parsing and counting logic. `SessionOrchestrator` gains pruning heuristic logic.
- **UI:** The TUI gains a new top-level pane and data tracking.

## Guidelines for Implementation
- **Git Status Parsing:** Use a simple regex or string splitting on the `git status -s` output format to map file paths to their status codes. Remember that paths in `git status` are relative to the git root.
- **Failure Heuristics:** To detect failed plans/reports, parse the file names (e.g., `*plan*.md`, `*report*.md`) and read their content directly using a fast string check (e.g., `Status: FAILURE`) rather than full markdown parsing to keep the orchestrator fast.
- **TUI Checkboxes:** Textual's `DataTable` doesn't have native checkboxes. You can simulate checkboxes using text icons (e.g., `[x]` vs `[ ]`) and handle the cell click event, or use a list of `Checkbox` widgets if the list is small enough.

## Implementation Notes
(To be filled during development)
