# Spec: Context Management UI and Auto-Pruning
- **Status:** Active

## Overview / Problem Statement
In interactive sessions, users currently lack visibility into the token footprint of their context files and lack a direct UI mechanism to prune context before generating the next plan. The current workflow (instructing the AI to `PRUNE` files) is inefficient. Furthermore, context tends to bloat over time with large files or failed execution reports, leading to wasted tokens.

This feature introduces a native "Context Management" section within the `TextualPlanReviewer` TUI, allowing users to manually toggle files for the *next* turn. It also introduces an "Auto-Pruning" system driven by configuration rules to intelligently pre-deselect problematic files.

## Guiding Principles / Core Logic
- **Forward-Looking:** Context modifications made during the review phase apply exclusively to the *next* turn's context (`turn.context`), not the current turn.
- **User Supremacy:** Auto-pruning rules only *pre-deselect* items in the TUI. The user always has the final say and can re-select an auto-pruned file before submitting.
- **Architectural Purity:** The `IPlanReviewer` must remain a pure function of `(Plan, ContextMetadata) -> Plan`. It must not directly mutate the filesystem. Unselected context items should be recorded in the `Plan` object's metadata for the `SessionOrchestrator` to process.

## Technical Specification
- **Domain Models:** Introduce `ContextItem` DTO to hold metadata for a single file (`path`, `token_count`, `source_scope`, `git_status`, `is_auto_pruned`). Update `ProjectContext` to include a list of these items.
- **Port Signatures:** Update `ILlmClient` to include a `count_tokens(text: str, model: str) -> int` method. Update `IPlanReviewer.review()` and `IRunPlanUseCase.execute()` to accept `project_context: Optional[ProjectContext] = None`.
- **Configuration:** Add an `auto_pruning` dictionary to `config.yaml` with the following granular controls:
  - `enabled: true/false`
  - `global_context_threshold: X` (Total token limit for turn context)
  - `prune_preceding_on_non_green: true/false` (Toggle for pruning turns preceding a 🔴/🟡 state)
  - `prune_validation_failures: true/false` (Toggle for pruning failed validation reports/plans)

## TUI Architecture & Data Flow
1. **ActionTree Node:** The TUI will feature a top-level node in the left-hand `ActionTree` called "Session Context".
2. **Context View:** When selected, the right pane displays an aggregate view (Total Tokens and Breakdown).
3. **Data Display:** Each item will display its path, token count, and git status (e.g., `M`, `U`, `??`).
4. **Toggling (No Checkboxes):** Toggling an item (via `Space` or click) alternates between its standard label and a "pruned" label using `[s dim]` (strikethrough and dimmed).
5. **Dynamic Totals:** The aggregate view MUST update in real-time as the user toggles items.
6. **Data Return:** When the user completes the review, any files toggled OFF are aggregated into a comma-separated string and attached to the returned `Plan` via `plan.metadata["pruned_context"]`.

## Auto-Pruning Heuristics
Auto-pruning evaluates files *before* rendering the TUI, setting their `is_auto_pruned` flag to `True`. The TUI renders these items with the `[s dim]` styling by default. The user maintains ultimate control and can re-activate them.

**Rules:**
1. **Scope Restriction:** Auto-pruning MUST ONLY apply to files in `turn.context`. `session.context` and System Prompts are strictly exempt.
2. **Global Budget Heuristic:** If `Total Context Tokens` > `config.global_context_threshold`, sort `turn.context` files by token count (descending) and prune largest files until the total is under the budget.
    - **Reason:** `Pruned to fit context budget`
3. **Failure History Heuristic:** If `prune_preceding_on_non_green` is enabled and a plan file (`turn-N-plan.md`) in `turn.context` has a 🔴 or 🟡 status emoji in its metadata header, prune the Plan and Report from the preceding turn (`turn-(N-1)`).
    - **Reason:** `Pruned as it led to a non-green state`
4. **Validation Failure Heuristic:** If a report file (`turn-N-report.md`) in `turn.context` contains `Status: Validation Failed`, prune both that report and its corresponding plan (`turn-N-plan.md`).
    - **Reason:** `Plan failed validation`
5. **Deleted File Heuristic:** If a file in the context has a git status of `D` (Deleted), it MUST be auto-pruned.
    - **Reason:** `File deleted from disk`
