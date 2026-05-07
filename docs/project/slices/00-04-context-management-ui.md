# Slice: Context Management UI
- **Status:** Planned
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Specs:** [context-management-ui.md](../specs/context-management-ui.md)
- **Prototype:** [prototypes/00-04/runner.py](../../../prototypes/00-04/runner.py)
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
And selecting it shows lists of context files grouped by scope (System/Session/Turn)
And each file displays its token count and git status
```

> As a user, I want the system to automatically deselect useless context files (like those leading to non-green states or exceeding a budget) so I don't waste tokens.
```gherkin
Given auto-pruning is enabled in the configuration
And a plan file in the context has a non-green (🔴/🟡) status
When the plan review TUI is launched
Then the previous turn's plan and report are shown but are struck through and dimmed
And files in the session context are never struck through automatically
```

## Deliverables
- [x] **Contract** - Add `get_text_token_count` to `ILlmClient`.
- [x] **Logic** - Implement `get_text_token_count` in `LiteLLMAdapter`.
- [x] **Contract** - Implement `ContextItem` DTO and update `ProjectContext` model.
- [x] **Contract** - Add `auto_pruning` default settings to `config.yaml`.
- [x] **Contract** - Update `IPlanReviewer.review` signature to accept `project_context`.
- [x] **Refactor** - Update `ConsolePlanReviewer` and `ExecutionOrchestrator` for `IPlanReviewer` signature expansion.
- [x] **Logic** - Update `ContextService` to build `ContextItem` list with git status and tokens.
- [x] **Logic** - Implement auto-pruning heuristics in `SessionOrchestrator`.
- [ ] **UI** - Implement "Session Context" tree population in `TextualPlanReviewer`.
- [ ] **UI** - Implement context item toggling and `[s dim]` styling.
- [ ] **UI** - Implement dynamic `ContextAggregateDetail` view.
- [ ] **Integration** - Update `ReviewerApp` to return `pruned_context` metadata.
- [ ] **Integration** - Update `SessionOrchestrator` to process `pruned_context` and delete files from turn context.
- [ ] **Wiring** - Verify end-to-end context visibility and auto-pruning (Gherkin scenarios).

## Implementation Notes
### Contract - Add get_text_token_count to ILlmClient
- Expanded `ILlmClient` with `get_text_token_count(text, model)`.
- Implemented as a non-breaking Expansion (throwing `NotImplementedError`) to allow incremental adapter updates without breaking the DI container.
- Added signature verification to `tests/suites/unit/core/ports/outbound/test_llm_client_contract.py`.

### Logic - Implement get_text_token_count in LiteLLMAdapter
- Overrode `get_text_token_count` in `LiteLLMAdapter` using `litellm.token_counter(text=text, ...)`.
- Refactored model resolution logic into a private `_resolve_model` helper to ensure consistency across `get_token_count`, `get_text_token_count`, and `get_context_window`.

### Contract - Implement ContextItem DTO and update ProjectContext model
- Introduced `ContextItem` dataclass for granular context file metadata (tokens, git status, scope, selection state).
- Expanded `ProjectContext` with `items`, `agent_name`, `system_prompt_tokens`, and `total_window`.
- Maintained backward compatibility via `field(default_factory=...)` for collection types and default literals for primitives.
- Verified immutability via `frozen=True` in unit tests.

### Contract - Add auto_pruning default settings to config.yaml
- Defined `auto_pruning` block in `src/teddy_executor/resources/config/config.yaml` with keys for `enabled`, `global_context_threshold`, `prune_preceding_on_non_green`, and `prune_validation_failures`.
- Sanitized `config.yaml` by removing `# pragma: allowlist secret` and setting the placeholder `api_key` to an empty string.
- Updated `tests/suites/unit/adapters/outbound/test_yaml_config_adapter.py` to verify the baseline contract using `fs.add_real_file` to map the actual bundled resource into the fake filesystem.

### Contract - Update IPlanReviewer.review signature to accept project_context
- Expanded `IPlanReviewer.review` signature to include `project_context: Optional["ProjectContext"] = None`.
- Used `TYPE_CHECKING` guard in the protocol file to avoid circular imports with the domain model.
- Verified the contract via `inspect.signature` in `tests/suites/unit/core/ports/inbound/test_plan_reviewer_contract.py`.
- Confirmed backward compatibility for existing implementations (`ConsolePlanReviewer`, `TextualPlanReviewer`) via global test suite execution.

### Logic - Update ContextService to build ContextItem list with git status and tokens
- Updated `ContextService` constructor to accept `ILlmClient` (Constructor Injection).
- Implemented `_parse_git_status` to transform `git status -s` output into a path -> status map.
- Applied Guideline: Mapped `??` (Untracked) to `U` for UI consistency.
- Updated `get_context` to iterate through all scoped paths and generate `ContextItem` objects with token counts and git status.
- Verified via unit tests that all files (including those in multiple scopes) are correctly captured and metadata is accurate.

### Logic - Implement auto-pruning heuristics in SessionOrchestrator
- Implemented `_apply_auto_pruning` in `SessionOrchestrator` using a multi-pass heuristic approach.
- Rules implemented:
    - **Global Budget:** Prunes largest files first to fit under `global_context_threshold`.
    - **Failure History:** Prunes turns preceding a 🔴/🟡 plan status.
    - **Validation Failure:** Prunes failed validation reports and their plans.
    - **Deleted File:** Prunes files with `D` git status.
    - **Individual Threshold:** Prunes files exceeding `threshold_tokens`.
- Hardened logic against shallow mocks in legacy tests via `is_dataclass` checks and safe numeric casting of configuration values.
- Resolved `UnboundLocalError` by ensuring all method-level imports (e.g., `re`) are scoped correctly and not trapped in conditional loops.
- Updated `TestEnvironment` harness to provide mandatory default token counts for `ILlmClient`.
- Refactored legacy integration tests to use the centralized harness, resolving wiring regressions.

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
    - `src/teddy_executor/adapters/inbound/textual_plan_reviewer_logic.py`:
        - Implement `rebuild_context_tree(app)` with a guard flag to prevent duplication.
        - Implement `update_context_detail(app, data)` to switch between aggregate and file-specific views.
        - Update `format_node_label` heuristics to handle `ContextItem` styling (bold paths, colored labels, grayed-out tokens).

## Guidelines for Implementation
- **Guarded TUI Build:** The `ReviewerApp` and `reviewer_logic` MUST implement a guarded build pattern (using a boolean flag like `_context_built`) to ensure the tree is populated exactly once. The base `ReviewerApp.on_mount` logic should be bypassed or cleared using `tree.clear()` before custom population.
- **Git Status Parsing:** Use `git status -s`.
    - Map `??` to `U` (Untracked) for visual consistency with modern IDEs.
    - Status colors: `M` (yellow), `U/A` (green), `D` (red).
- **Failure Heuristics:**
    - **Non-Green State:** Parse plan headers in `turn.context` for `Status: ... 🔴` or `Status: ... 🟡`. If found, prune the *preceding* turn's artifacts.
    - **Validation Failure:** Check report files in `turn.context` for the string `Status: Validation Failed`. If found, prune that report and its plan.
    - **Deleted File:** Check `ContextItem.git_status` for `D`. If found, prune the item.
- **Auto-Prune Reasons:** Use the following standardized strings for the `auto_prune_reason` metadata:
    - `Pruned to fit context budget`
    - `Plan failed validation`
    - `Pruned as it led to a non-green state`
    - `File deleted from disk`
- **Dynamic UI Logic:** Every toggle of a context item MUST trigger a recalculation and refresh of the `ContextAggregateDetail` view.
- **Context Management Tree:**
    - Use a flat tree structure with leaf-only label nodes (`SYSTEM_LABEL`, `SESSION_LABEL`, `TURN_LABEL`) as siblings under the root.
    - **Hierarchy (Prototype Standard):** Labels use `[#888888 italic]Scope:[/]` formatting. File items are siblings of labels but use **two leading spaces** in their label strings for visual indentation.
    - **Visual Cues:**
        - **Standard format:** `  [bold]path[/] [[color]status[/]] [#888888]tokens[/]` (e.g., `  [bold]src/core.py[/] [[yellow]M[/]] [#888888]1.2k[/]`).
        - **Pruned format:** `  [s dim]path [[color]status[/]] tokens[/]`. The entire string (path, status, and tokens) MUST be struck through.
    - **Editor Integration (`e` key):**
        - **Agent Node:** Opening the `e` (edit) key on an Agent node MUST launch a TUI Modal (`PromptEditorModal`) containing a `TextArea` for direct XML prompt editing.
        - **Context Labels/Files:** Opening `e` on a session/turn label or a specific context file MUST launch the external editor (using `ConsoleTooling.get_editor()`).
        - **Deferred Harvest:** The TUI MUST wait for the external process to exit, then perform a "Deferred Harvest": re-read the `.context` files from disk and refresh the `ContextItem` metadata (tokens, git status) and the UI tree dynamically.
    - **Navigation (`alt+up/down`):** Refine `ActionTree.jump_to_section` to include the Context root. Navigation should jump between the Context root, Rationale root, and Action Plan root.
    - **Right Pane Summary:**
        - Include a bulleted breakdown of the context: `• System`, `• Session`, `• Turn`.
        - Show the token count for each (e.g., `• System: 2.5k`).
        - Indent breakdown items with `• ` (bullet) but NO additional leading spaces. NO empty line between header and list.
    - **Smart Hierarchy:**
        - Keep headers (`System:`, `Session:`, `Turn:`) and files as siblings under the Context root to avoid over-nesting depth.
        - Use **two leading spaces** in file labels to simulate indentation.
    - Display Git Status in full words (e.g., "Modified", "Untracked") in the right-side detail pane.
