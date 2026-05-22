# Bug: Validation Failure Context Reset
- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../../milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** N/A
- **Specs:** [interactive-session-workflow.md](../../specs/interactive-session-workflow.md)

## Symptoms
Expected: When a plan fails validation, the "replanning" turn should include the full conversation history plus the validation error.
Actual: The context token count drops to initial session levels (e.g., from 30.5k to 17.7k), suggesting history loss during the replan turn.

## Context & Scope
### Regressing Delta
[TBD: Likely within recent session orchestration or replanning logic.]

### Environmental Triggers
- Non-interactive session mode (reported, potentially affects interactive).
- Plan validation failure.

### Ruled Out
- [TBD]

## Diagnostic Analysis
### Causal Model
1. **Automated Replanning**: `SessionReplanner.trigger_replan_turn` is invoked upon validation failure. It triggers `PlanningService.generate_plan` but fails to resolve/pass `context_files`.
2. **Context Fallback**: `PlanningService.generate_plan` receives a `turn_dir` but lacks internal logic to resolve context manifests. It passes `context_files=None` to `ContextService`.
3. **History Loss**: `ContextService` falls back to `FileSystemManager.get_context_paths()`, which only returns global `.teddy/*.context` files, ignoring the `turn.context` in the session directory that contains the history of previous turns.
4. **Interactive Contrast**: `SessionPlanner.trigger_new_plan` (used in interactive mode) *does* explicitly resolve and pass these manifests, explaining why the bug is more prominent in automated replanning.

### Discrepancies
- `SessionReplanner.trigger_replan_turn` (Resolved: Fails to resolve context manifests before calling planning service).
- `PlanningService.generate_plan` (Resolved: Lacks defensive auto-resolution of context from `turn_dir`).

### Investigation History
1. Initial report: Observed context token drop from 30.5k to 17.7k (initial state) after "Validation failed... replanning" message.
2. Code Analysis: `SessionOrchestrator` delegates to `SessionLifecycleManager.trigger_replan` upon validation failure. `SessionService.transition_to_next_turn` contains the logic for carrying forward `plan.md` and `report.md` into the next turn's context.
3. Hypothesis: `PlanningService.generate_plan` (called during replan) invokes `ContextService.get_context` without `context_files`. If `ContextService` doesn't automatically resolve turn context, history is lost.
4. Verified: `LocalFileSystemAdapter.get_context_paths` is global-only, confirming that if `context_files` is `None`, turn-specific history is ignored.
5. MRE: Created `spikes/debug/01-validation-context-reset-mre.py` to confirm that `PlanningService` fails to resolve context paths when generating a plan from a turn directory.
6. Hypothesis Refinement: The bug likely affects all new plan generation within sessions (including interactive mode) because `PlanningService.generate_plan` lacks logic to auto-resolve turn context.
7. Shadow Verification: Created `spikes/debug/shadow_planning_service.py` with defensive context resolution logic. MRE verified that this fix correctly resolves and passes context manifests when triggered via the automated replan path.
8. Systemic Audit: Audited `SessionReplanner` and `PlanningService`. Confirmed that `SessionReplanner` is the primary culprit but `PlanningService` requires defensive resolution to prevent this class of bug across all session-aware consumers.

## Solution
### Root Cause
The `SessionReplanner` triggers a replan by calling `PlanningService.generate_plan` but fails to resolve and pass the session/turn context manifests. `PlanningService` assumes the caller provides these manifests and defaults to global context if they are missing. This results in a "context reset" where the LLM loses all turn history.

### Verified Fix
Introduce defensive context resolution in `PlanningService.generate_plan`. If `context_files` is `None` but a `turn_dir` is provided, the service should use the `SessionManager` to resolve the standard manifests (`session.context`, `turn.context`) from that directory before gathering context.

### Systemic Prevention
The root cause belongs to the **"Incomplete State Propagation"** category. To prevent this, services that operate on session turns should either:
1. Mandate context manifests in their contract (if the caller is an orchestrator).
2. Internally resolve standard manifests if provided a turn directory (defensive design).

We will adopt the defensive design in `PlanningService` to make it more robust for future session-aware consumers.
