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
  - `threshold_tokens: X`
  - `prune_failed_plans: true/false`
  - `prune_failed_reports: true/false`

## TUI Architecture & Data Flow
1. **ActionTree Node:** The TUI will feature a top-level node in the left-hand `ActionTree` called "Session Context".
2. **Context View:** When selected, the right pane displays a `ContextManagementView`. This view MUST distinctly separate `session.context` files (pinned, un-prunable by auto-rules) and `turn.context` files (dynamic).
3. **Data Display:** Each item will display its path, token count, git status (e.g., `M`, `U`, `??`), and a checkbox.
4. **Data Return:** When the user completes the review, any files toggled OFF are aggregated into a comma-separated string and attached to the returned `Plan` via `plan.metadata["pruned_context"]`.

## Auto-Pruning Heuristics
Auto-pruning evaluates files *before* rendering the TUI, setting their `is_auto_pruned` flag to `True`. The TUI renders these items as unchecked by default. The user maintains ultimate control and can re-check them.

**Rules:**
1. **Scope Restriction:** Auto-pruning MUST ONLY apply to files in `turn.context`. Files in `session.context` are strictly exempt.
2. **Configuration Gate:** Must respect the `auto_pruning.enabled` config toggle.
3. **Token Threshold:** Files exceeding the `threshold_tokens` limit are flagged.
4. **Failure Artifacts:** The orchestrator must heuristically identify artifacts based on the granular toggles:
    - If `prune_failed_plans` is true: flag plans that failed validation.
    - If `prune_failed_reports` is true: flag execution reports with non-green status (e.g., FAILURE or ABORTED), and their corresponding plans.
