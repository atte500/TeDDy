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
(To be defined by the Architect)
- **Domain Models:** Updates to `ProjectContext` to hold token metadata.
- **Configuration:** New schema elements for `auto_prune_threshold`, etc.
- **Port Signatures:** Updates to `IPlanReviewer` and orchestrator data flow.
- **TUI Architecture:** How the `ActionTree` will render the context and translate selections.

## Guidelines
For the Architect:
1. Map the exact data flow of token counts from `ContextService` to the TUI.
2. Define how the TUI's context selections are passed back out (e.g., synthetic `PRUNE` actions vs. a `pruned_context` metadata list).
3. Design the integration point for Auto-Prune rules. Where should they be evaluated? (Hint: likely in the Orchestrator before passing data to the TUI).
