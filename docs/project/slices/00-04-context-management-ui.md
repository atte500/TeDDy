# Slice: Context Management UI
- **Status:** Planned
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Specs:** [context-management-ui.md](../specs/context-management-ui.md)
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
- **Domain Models:**
    - `src/teddy_executor/core/domain/models/project_context.py`: Implement `ContextItem` dataclass with `path`, `token_count`, `git_status`, `scope`, `selected`, and `auto_prune_reason`.
    - `ProjectContext`: Update to include `items: List[ContextItem]`, `agent_name: str`, `system_prompt_tokens: int`, and `total_window: int`.
- **Ports:**
    - `src/teddy_executor/core/ports/outbound/llm_client.py`: Add `get_text_token_count(text: str, model: Optional[str] = None) -> int`.
    - `src/teddy_executor/core/ports/inbound/plan_reviewer.py`: Update `review()` to accept `project_context: Optional[ProjectContext]`.
- **Migration (Shared Seams):**
    - `src/teddy_executor/core/services/execution_orchestrator.py`: Update the call to `self._plan_reviewer.review(plan)` to pass `project_context`.
    - `src/teddy_executor/adapters/inbound/console_plan_reviewer.py`: Update implementation of `review()` to accept the optional `project_context` argument (Expansion).
- **Adapters:**
    - `src/teddy_executor/adapters/outbound/litellm_adapter.py`: Implement `get_text_token_count` using `litellm.token_counter(text=text, ...)`.
    - `src/teddy_executor/adapters/inbound/textual_plan_reviewer_app.py`: Store `ProjectContext` in `ReviewerApp.__init__` and pass it to `on_mount_logic`.
- **Services:**
    - `src/teddy_executor/core/services/context_service.py`: Update `get_context` to iterate through `scoped_paths`, count tokens per file using `ILlmClient`, and parse `git_status` output into clean 2-char codes for `ContextItem`s.
    - `src/teddy_executor/core/services/session_orchestrator.py`: In `execute()`, call `context_service.get_context()`, apply pruning heuristics (check file patterns for `FAILURE`, token thresholds from config), and pass the enriched `ProjectContext` to the reviewer.
- **UI Logic:**
    - `src/teddy_executor/adapters/inbound/textual_plan_reviewer_logic.py`: Update `on_mount_logic` to iterate over `project_context.items` and build the tree structure (System/Session/Turn sections with sibling indentation) as proven in the prototype.

## Guidelines for Implementation
- **Git Status Parsing:** Use a simple regex or string splitting on the `git status -s` output format to map file paths to their status codes. Remember that paths in `git status` are relative to the git root.
- **Failure Heuristics:** To detect failed plans/reports, parse the file names (e.g., `*plan*.md`, `*report*.md`) and read their content directly using a fast string check (e.g., `Status: FAILURE`) rather than full markdown parsing to keep the orchestrator fast.
- **Auto-Prune Reasons:** Use the following standardized strings for the `auto_prune_reason` metadata:
    - `Exceeds 15k token limit`
    - `Failed plan validation`
    - `Non-green plan`
- **Context Management Tree:**
    - Use a flat tree structure with leaf-only label nodes (`SESSION_LABEL`, `TURN_LABEL`, `SYSTEM_LABEL`) for grouping.
    - **Visual Cues:**
        - Use VS Code-style colorization for Git statuses in the tree (e.g., `[yellow]M [/yellow]`, `[green]??[/green]`).
        - Auto-pruned files (identified by heuristics) MUST be rendered with `[s dim]` (ultra-dimmed strikethrough) by default.
    - **Editor Integration (`e` key):**
        - **Agent Node:** Opening the `e` (edit) key on an Agent node MUST launch a TUI Modal (`PromptEditorModal`) containing a `TextArea` for direct XML prompt editing.
        - **Context Labels/Files:** Opening `e` on a session/turn label or a specific context file MUST launch the external editor (using `ConsoleTooling.get_editor()`).
        - **Deferred Harvest:** The TUI MUST wait for the external process to exit, then perform a "Deferred Harvest": re-read the `.context` files from disk and refresh the `ContextItem` metadata (tokens, git status) and the UI tree dynamically.
    - **Navigation (`alt+up/down`):** Refine `ActionTree.jump_to_section` to include the Context root. Navigation should jump between the Context root, Rationale root, and Action Plan root.
    - **Right Pane Summary:**
        - Include a bulleted breakdown of the context: `• System`, `• Session`, `• Turn`.
        - Show the token count for each (e.g., `• System: 2.5k`).
        - Use an empty line separation between the Total Context and the breakdown list.
        - Indent breakdown items with `• ` (bullet) but NO additional leading spaces.
    - **Smart Hierarchy & Visuals:**
        - Implement "Smart Hierarchy" by keeping headers (`System:`, `Session:`, `Turn:`) and files as siblings under the Context root to avoid over-nesting depth.
        - Use **two leading spaces** in file labels to simulate indentation.
        - When an item is auto-pruned/deselected, apply ultra-low visibility: use near-black color `#333333` combined with `dim` and `strikethrough`.
        - Ensure leading spaces are **not** struck through.
    - Display Git Status in full words (e.g., "Modified", "Untracked") in the right-side detail pane.

## Implementation Notes
(To be filled during development)
