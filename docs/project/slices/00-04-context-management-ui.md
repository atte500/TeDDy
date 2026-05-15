# Slice: Context Management UI & Session Loop Repair
- **Status:** Planned
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Specs:** [context-management-ui.md](../specs/context-management-ui.md)
- **Prototype:** [prototypes/00-04/runner.py](../../../prototypes/00-04/runner.py)
- **MRE:** [spikes/debug/03_repro_session_break.py](../../../spikes/debug/03_repro_session_break.py)
- **Showcase:** [spikes/showcases/00-04/showcase_heuristics.sh](../../../spikes/showcases/00-04/showcase_heuristics.sh)
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

> As a user, I want the system to automatically prune turns older than my retention limit so I don't waste tokens on stale context.
```gherkin
Given an interactive session is at Turn 30
And "max_turns_retention" is set to 25
When the plan review TUI is launched
Then Turn 5 and all preceding turns are deselected
And those items display the reason "Turn exceeds retention limit of 25"
And Turn 6 and subsequent turns remain selected by default
And files with "System" or "Session" scope are NOT deselected by the retention limit
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
- [x] **UI** - Implement "Session Context" tree population in `TextualPlanReviewer`.
- [x] **UI** - Implement context item toggling and `[s dim]` styling.
- [x] **UI** - Implement dynamic `ContextAggregateDetail` view.
- [x] **Integration** - Update `ReviewerApp` to return `pruned_context` metadata.
- [x] **Integration** - Update `SessionOrchestrator` to process `pruned_context` and delete files from turn context.
- [x] **Wiring** - Verify end-to-end context visibility and auto-pruning (Gherkin scenarios).
- [x] **Logic (Refinement)** - Implement Recovery Cleanup (prune failure context only when turn returns to 🟢).
- [x] **Logic (Refinement)** - Update Validation Matching to target `- **Overall Status:** Validation Failed`.
- [x] **Logic (Refinement)** - Update standardized auto-prune reason to "Pruned failure history after successful recovery".
- [x] **Cleanup (Refinement)** - Remove individual token threshold logic and related config keys.
- [x] **Logic (Refinement)** - Normalize slashes in `is_path_in_context` to support Windows paths.
- [x] **Logic (Refinement)** - Update `_extract_resource_path` in `SessionService` to normalize extracted paths.
- [x] **Logic (Refinement)** - Implement `_apply_retention_limit` in `SessionPruningService` (Default: 25).
- [x] **Contract** - Add `max_turns_retention: 25` to `config.yaml`.
- [x] **Showcase** - Create `showcases/00-04/showcase_heuristics.sh` to demonstrate failure-streak preservation, post-green cleanup, and retention limits.
- [x] **Contract** - Update `SessionPruningService.prune` signature to accept `current_status: Optional[str]`.
- [x] **Logic** - Refactor `SessionPruningService` to use regex-anchored status detection targeting the `- **Status:**` line.
- [x] **Logic** - Update `SessionPruningService` heuristics to trigger recovery cleanup immediately if `current_status` is green.
- [x] **Wiring** - Update `SessionOrchestrator.execute` to pass the plan status to the pruning service.
- [x] **Refactor** - Refactor `extract_status_emoji` in `textual_plan_reviewer_helpers.py` to use anchored regex targeting the status line.
- [x] **Logic** - Implement initial_request.md persistence at the session root in `SessionService.create_session`.
- [x] **Logic** - Update `SessionService` to seed `initial_request.md` into the `session.context` file and allow it to be pruned via the TUI.
- [ ] **Cleanup** - Remove legacy "User Request" extraction logic from `SessionPlanner` and `PromptManager`.
- [ ] **Logic** - Refactor `PromptManager` to treat `initial_request.md` as context and prioritize turn-specific feedback (the `m` key).
- [ ] **Logic** - Remove instruction injection from `PlanningService.generate_plan` (keeping `input.md` as pure project state).
- [ ] **Wiring** - Verify end-to-end `initial_request.md` visibility in the TUI Context Tree (Session Scope).
- [x] **Wiring** - Verify that all symptoms of Session Loop Breakage are resolved using the provided MRE.

## Implementation Notes

### Session Loop Breakage & Path Resolution
- **Root Cause**: Inconsistent path resolution between `SessionService` and `PlanningService` caused context files (like `session.context`) to be unresolvable or incorrectly re-based during session resume loops.
- **Path Logic Fix**: Standardized `LocalFileSystemAdapter._resolve_path` to handle absolute paths (crucial for `pytest` `tmp_path` compatibility) while strictly normalizing relative paths against the project root.
- **macOS/Performance Optimization**: Optimized `_resolve_path` to avoid redundant `Path.resolve()` calls unless symlinks or `..` components are detected. This fixed resolution hangs on macOS and drastically improved file scanning performance.
- **Context Strategy**: `PlanningService` now explicitly registers `session.context` via `SessionService`, ensuring goal persistence across turns.

### Performance & Parallelization
- **Issue**: Token counting for large repositories (>500 files) was exceeding the 1.0s threshold due to sequential execution.
- **Fix**: Implemented `ThreadPoolExecutor` in `ContextService._get_path_to_tokens` to parallelize token count requests. This reduced execution time for 500 files from ~3.7s to ~0.5s.

### Test Resilience
- Updated brittle unit tests in `SessionService` (e.g., `test_create_session_seeds_initial_request_into_session_context`) to handle fully qualified paths instead of exact filename matches, ensuring resilience against the standardized path resolution strategy.
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
    - **Recovery Cleanup:** Prunes all 🔴/🟡 turns once a 🟢 status is achieved.
    - **Validation Failure:** Prunes failed validation reports (matching `- **Overall Status:** Validation Failed`) and their plans.
    - **Deleted File:** Prunes files with `D` git status.
- Hardened logic against shallow mocks in legacy tests via `is_dataclass` checks and safe numeric casting of configuration values.
- Resolved `UnboundLocalError` by ensuring all method-level imports (e.g., `re`) are scoped correctly and not trapped in conditional loops.
- Updated `TestEnvironment` harness to provide mandatory default token counts for `ILlmClient`.
- Refactored legacy integration tests to use the centralized harness, resolving wiring regressions.

### UI - Implement "Session Context" tree population in TextualPlanReviewer
- Implemented `_build_context_section` in `textual_plan_reviewer_logic.py` to inject the new "Context" section before the "Rationale" section.
- Added support for grouped context items by scope (System/Session/Turn).
- Implemented `_format_context_item_label` with Prototype-compliant Rich formatting:
    - **Path:** Bold.
    - **Status:** Color-coded (M: yellow, U/A: green, D: red).
    - **Tokens:** Grayed out.
    - **Indentation:** 2 leading spaces for file items.
- Introduced `_tree_built` guard in `on_mount_logic` using an explicit `is True` check to support `MagicMock` in unit tests.
- Synchronized top-level section identifiers (`CONTEXT_ROOT`, `RATIONALE_ROOT`, `ACTION_PLAN_ROOT`) as constants to ensure robustness in navigation and detail views.
- Updated initial cursor logic to focus the "Context" root if `ProjectContext` is present.

### UI - Implement context item toggling and [s dim] styling
- Removed `frozen=True` from `ContextItem` to allow TUI-side state management of the `selected` property.
- Updated `toggle_selection_logic` to handle `ContextItem` data, flipping the `selected` state.
- Updated `refresh_node_logic` to correctly call `_format_context_item_label` for `ContextItem` nodes.
- Updated `check_action_logic` to permit `toggle_selection` and navigation actions for `ContextItem` nodes while disabling action-specific logic (execute/revert).
- Verified toggling and styling behavior via unit test `test_reviewer_app_toggles_context_item`, asserting on the Rich markup of the updated node label.

### UI - Implement dynamic ContextAggregateDetail view
- Expanded `_update_detail_view` in `textual_plan_reviewer_logic.py` to handle `CONTEXT_ROOT`, scope labels (`SYSTEM_LABEL`, etc.), and `ContextItem` data.
- Implemented Aggregate View showing:
    - **Total Tokens:** Formatted as `X.Yk / Zk tokens` (actual vs budget).
    - **Scope Breakdown:** Formatted with `• ` bullets and k-unit tokens for System, Session, and Turn.
- Implemented `ContextItem` detail view showing Path, Tokens (k-formatted), Git Status (Human-readable map: e.g., `M` -> `Modified`), Scope, and `auto_prune_reason`.
- Implemented `SYSTEM_PROMPT` detail view showing Agent name and token count.
- Verified via unit tests (`test_reviewer_app_shows_context_aggregate_detail` and `test_reviewer_app_shows_context_item_detail`) that navigation correctly updates the right pane with expected formatted strings.

### Integration - Update ReviewerApp to return pruned_context metadata
- Updated `ReviewerApp.action_submit` to harvest paths of unselected `ContextItem` objects from `project_context`.
- Collected paths are injected into `plan.metadata["pruned_context"]` as a comma-separated string.
- If no files are pruned, the key is removed from metadata to maintain a clean plan state.
- Resolved a `MountError` in `textual_plan_reviewer_logic.py` by adding an `is_attached` guard to `_update_detail_view`. This prevents premature widget mounting during the initial TUI refresh when a complex `project_context` is present.
- **[DEBT]** Noted that `_update_detail_view` complexity (10/9) and `textual_plan_reviewer_app.py` length (307/300) now exceed quality gates. Logged for structural refactoring in Milestone 10.

### Wiring - Verify end-to-end context visibility and auto-pruning
- Verified the end-to-end data flow from `SessionOrchestrator` through `ExecutionOrchestrator` to the `ReviewerApp`.
- Implemented behavioral acceptance tests in `tests/suites/acceptance/test_context_management_ui.py`.
- Verified that the "Context" node and its children are correctly populated with Rich styling (bold paths, colored status, grayed tokens).
- Verified that auto-pruned items (e.g. failed plans) are correctly rendered with `[dim strike]` formatting.
- Confirmed that toggling selection in the TUI correctly updates the `pruned_context` metadata in the submitted plan.

### Logic (Refinement) - Recovery Cleanup & Regression Fixes
- Implemented Recovery Cleanup heuristic in `SessionOrchestrator`: Prunes all preceding 🔴/🟡 turns and their reports once a 🟢 status is achieved.
- Refined `_is_validation_failure` matching to target the specific string `- **Overall Status:** Validation Failed`.
- Removed deprecated `individual_token_threshold` logic and related config keys to simplify the pruning budget.
- Hardened `TestEnvironment` with `without_reviewer()` to support legacy interactor-based acceptance tests. This helper re-registers the `ExecutionOrchestrator` without a reviewer, forcing the fallback to `IUserInteractor`.
- Resolved isolation relaxation regression in `test_orchestrator_allows_non_isolated_terminal_action` by explicitly providing the `mock_plan_reviewer` to the orchestrator fixture.

### Logic (Refinement) - Normalize slashes in is_path_in_context
- Updated `is_path_in_context` in `src/teddy_executor/core/services/validation_rules/helpers.py` to normalize both target and context paths by replacing backslashes with forward slashes.
- Stripped leading slashes consistently across comparison.
- Added dedicated unit tests in `tests/suites/unit/core/services/test_validation_helpers.py` covering Windows-style paths, mixed slashes, and scope respect.

### Logic (Refinement) - Update _extract_resource_path in SessionService
- Updated `_extract_resource_path` in `src/teddy_executor/core/services/session_service.py` to normalize extracted paths to forward slashes.
- Applied `replace("\\", "/")` to both Markdown link matches and raw string fallbacks.
- Ensured leading slashes are stripped consistently post-normalization.
- Added granular unit tests in `tests/suites/unit/core/services/test_session_service_extraction.py`.

### Logic (Refinement) - Implement _apply_retention_limit in SessionPruningService
- Implemented `_apply_retention_limit` using the existing `_extract_turn_id` helper.
- The heuristic identifies the maximum Turn ID present in the context and prunes any items with `Turn` scope where `turn_id <= (max_id - retention_limit)`.
- Added `max_turns_retention: 25` to the bundled `config.yaml`.
- Verified via unit tests that System and Session scoped items are strictly exempt from this limit.

### Logic (Refinement) - Update SessionPruningService Contract & Logic for current_status
- Expanded `SessionPruningService.prune` to accept an optional `current_status` string.
- Refactored `Recovery Cleanup` heuristic to trigger immediately if `current_status` contains "🟢", allowing the system to prune preceding failure history as soon as a turn returns to a success state.
- Hardened unit tests to use strictly numeric turn directories (e.g., `01/plan.md`) to match the service's extraction regex.

### Wiring - SessionOrchestrator Status Propagation
- Updated `SessionOrchestrator.execute` to extract `Status` from plan metadata and pass it to the `pruning_service.prune` method.
- Refactored `SessionOrchestrator` unit test fixture to use a mock context service, resolving `AttributeError` regressions during dependency injection testing.

### Refactor - Refine Status Emoji Extraction
- Refactored `extract_status_emoji` to prioritize anchored status lines (`- **Status:**`) using `re.search` with `re.MULTILINE`.
- Implemented first-match fallback for unanchored strings to ensure poisoning resilience (e.g., ignoring emojis in parenthetical notes).
- Synchronized the detection pattern with `SessionPruningService` to ensure a consistent "Source of Truth" for status throughout the session lifecycle.

### Logic - Refactor SessionPruningService status detection
- Implemented `_check_plan_failed` using `re.search(r"^- \*\*Status:\*\*.*[🔴🟡]", content, re.MULTILINE)`.
- Implemented `_check_report_failed_validation` using `re.search(r"^- \*\*Overall Status:\*\* Validation Failed", content, re.MULTILINE)`.
- These anchored regexes prevent false positives from emojis or "Validation Failed" strings appearing in rationales or user notes.
- Updated `test_session_pruning_windows.py`, `test_session_pruning_robustness.py`, and `test_context_management_ui.py` to use protocol-compliant status strings in mocks.

### Logic - Implement initial_request.md persistence at the session root
- Expanded `ISessionManager` protocol and `SessionService.create_session` implementation to accept an optional `initial_request` string.
- Implemented file writing logic to save the request as `initial_request.md` in the session root directory during bootstrap.
- Verified via unit tests that the file is correctly placed alongside `session.context` and that the implementation handles optionality gracefully.

### Logic - Seed initial_request.md into session.context
- Updated `SessionService.create_session` to append `initial_request.md` to the `clean_context` string if an `initial_request` is provided.
- Reordered the `session.context` write operation to occur after the initial request check.
- Verified via unit tests that the request file is correctly registered in the session context, enabling its visibility in the TUI under the `Session` scope.

## Technical Debt
- **[DEBT]** Harness Complexity: `without_reviewer()` in `TestEnvironment` is a manual container re-wiring. Consider a more robust `interactive_mode` configuration (e.g., `"tui" | "console"`) for the harness to toggle between `IPlanReviewer` and `IUserInteractor` cleanly.
- **[DEBT]** Orchestrator Size: `ExecutionOrchestrator` is approaching the 300-line limit and has high cyclomatic complexity in its execution loop.

## Delta Analysis
- **Domain Models:**
    - `src/teddy_executor/core/domain/models/project_context.py`: Implement `ContextItem` dataclass with `path`, `token_count`, `git_status`, `scope`, `selected`, and `auto_prune_reason`.
    - `ProjectContext`: Update to include `items: List[ContextItem]`, `agent_name: str`, `system_prompt_tokens: int`, and `total_window: int`.
- **Ports:**
    - `src/teddy_executor/core/ports/outbound/llm_client.py`: Add `get_text_token_count(text: str, model: Optional[str] = None) -> int`.
    - `src/teddy_executor/core/ports/inbound/plan_reviewer.py`: Update `review()` to accept `project_context: Optional[ProjectContext]`.
- **Adapters:**
    - `src/teddy_executor/adapters/outbound/litellm_adapter.py`: Implement `get_text_token_count` using `litellm.token_counter(text=text, ...)`.
    - `src/teddy_executor/adapters/inbound/textual_plan_reviewer_app.py`: Store `ProjectContext` in `ReviewerApp.__init__` and pass it to `on_mount_logic`.
- **Services:**
    - `src/teddy_executor/core/services/session_service.py`:
        - Update `create_session` to initialize `00/initial_request.md`.
        - Update `transition_to_next_turn` to ensure `00/initial_request.md` is always in the context set.
    - `src/teddy_executor/core/services/planning_service.py`:
        - Remove `input.md` instruction injection.
        - Pass `user_message` to `PromptManager` for metadata persistence.
    - `src/teddy_executor/core/services/prompt_manager.py`:
        - Implement `meta.yaml` persistence for `user_request`.
        - Remove regex-based instruction extraction from reports.
        - Update `resolve_message` to prioritize `meta.yaml` feedback.
    - `src/teddy_executor/core/services/context_service.py`: Update `get_context` to iterate through `scoped_paths`, count tokens per file using `ILlmClient`, and parse `git_status` output into clean 2-char codes for `ContextItem`s.
- **UI Logic:**
    - `src/teddy_executor/adapters/inbound/textual_plan_reviewer_logic.py`:
        - Implement `rebuild_context_tree(app)` with a guard flag to prevent duplication.
        - Implement `update_context_detail(app, data)` to switch between aggregate and file-specific views.
        - Update `format_node_label` heuristics to handle `ContextItem` styling (bold paths, colored labels, grayed-out tokens).

## Guidelines for Implementation

### Session Root Goal Protocol
- **Bootstrap:** `SessionService.create_session` MUST accept the initial user message and save it as `initial_request.md` at the session root (sibling to `session.context`).
- **Context Seeding:** The path `initial_request.md` MUST be appended to the `session.context` file during bootstrap. This ensures it is treated as a standard context item with `Session` scope.
- **TUI Visibility:** `initial_request.md` MUST be visible in the "Session Context" tree under the `Session` scope. Users can prune it or edit it using the `e` key to update the "Session Goal" dynamically.

### Instruction Lifecycle & Transparency
- **Pure input.md:** `PlanningService` MUST NOT inject the user request into the `input.md` content. The `input.md` file remains a pure snapshot of the file tree and relevant file contents.
- **Metadata-Driven Resumption:** `PromptManager.resolve_message` MUST prioritize turn-specific feedback stored in the current turn's `meta.yaml` (key: `user_request`). If no feedback is present, it relies on the goal being present in the `turn.context`.
- **Machine-Readable Goal:** `PromptManager.update_meta` MUST save the `user_request` to the `meta.yaml` file to ensure `teddy resume` can function without re-parsing Markdown reports.
- **Human-Readable Audit:** The `ExecutionReportAssembler` continues to populate the `user_request` field from metadata, ensuring the report remains a complete, self-contained record of the turn.

### TUI Context Management
- **Guarded TUI Build:** The `ReviewerApp` and `reviewer_logic` MUST implement a guarded build pattern (using a boolean flag like `_context_built`) to ensure the tree is populated exactly once. The base `ReviewerApp.on_mount` logic should be bypassed or cleared using `tree.clear()` before custom population.
- **Git Status Parsing:** Use `git status -s`.
    - Map `??` to `U` (Untracked) for visual consistency with modern IDEs.
    - Status colors: `M` (yellow), `U/A` (green), `D` (red).
- **Failure Heuristics:**
    - **Recovery Cleanup:** If current turn is 🟢, scan context for any `plan.md` files with `Status: ... 🔴` or `Status: ... 🟡`. If found, prune them and their corresponding reports.
        - **Robustness:** Detection MUST target only the `- **Status:**` line using regex `r"^- \*\*Status:\*\*.*"` to avoid rationales or code blocks.
        - **Immediate Trigger:** The `prune` service MUST be aware of the current plan's status to trigger cleanup without a 1-turn lag.
    - **Validation Failure:** Check report files in `turn.context` for the specific string `- **Overall Status:** Validation Failed`. If found, prune that report and its plan.
    - **Deleted File:** Check `ContextItem.git_status` for `D`. If found, prune the item.
- **Auto-Prune Reasons:** Use the following standardized strings for the `auto_prune_reason` metadata:
    - `Pruned to fit context budget`
    - `Plan failed validation`
    - `Pruned failure history after successful recovery`
    - `File deleted from disk`
    - `Turn exceeds retention limit of {N}`
- **Retention Limit Logic:**
    - Use `_extract_turn_id` to identify turn numbers.
    - Calculate the maximum turn ID present in the context.
    - Deselect any turn where `turn_id <= (max_id - retention_limit)`.
    - This rule MUST strictly apply only to `Turn` scope items.
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
