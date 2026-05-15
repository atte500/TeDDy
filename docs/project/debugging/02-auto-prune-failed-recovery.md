# Bug: Auto-Pruning Fails to Identify 🔴/🟡 Turns for Recovery Cleanup

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** [00-04-context-management-ui](../slices/00-04-context-management-ui.md)
- **Specs:** [context-management-ui.md](../specs/context-management-ui.md)

## Symptoms
Expected behavior: When the current turn is 🟢 (Success), preceding turns with 🔴 (Failure) or 🟡 (Warning) status should be auto-pruned from the context.
Actual behavior: Failed turns (plans and reports) remain selected in the context even after a successful turn.

## Context & Scope
### Regressing Delta
Unknown. This appears to be a flaw in the initial implementation of the "Recovery Cleanup" heuristic in Milestone 10, Slice 4 or 8.

### Environmental Triggers
- Interactive session active.
- Current turn status is 🟢.
- Context contains preceding `turn-N-plan.md` and `turn-N-report.md` files where status was 🔴 or 🟡.

### Ruled Out
- TUI rendering (The issue is in the heuristic selection state, not the display).

## Diagnostic Analysis
### Causal Model
1. `SessionOrchestrator` calls `SessionPruningService.prune(project_context)`.
2. `SessionPruningService._identify_turns_to_prune` calculates statuses and identifies turns to deselect.
3. If the latest turn is 🟢, preceding 🔴/🟡 turns are marked for pruning.
4. It parses report files to find status.
5. It should mark corresponding plans and reports as `selected = False`.

### Discrepancies
- Preceding failed turns are not being marked as `selected = False`. (Resolved: Confirmed fragility and 1-turn lag due to lack of current-turn awareness).

### Investigation History
1. Initializing Case File.
2. Searching for pruning logic. Located `SessionPruningService`.
3. Analyzing `SessionPruningService` revealed fragile emoji detection using `any(p in content for p in patterns)`.
4. MRE `spikes/debug/02_repro_prune.py` PROVED fragility: 🔴 in rationale causes a SUCCESS turn to be treated as FAILURE.
5. Created Shadow File `spikes/debug/shadow_session_pruning_service.py` with regex-based status detection and `current_status` awareness.
6. Verified fix in sandbox: MRE passes robustness and immediate cleanup tests.

## Solution
### Root Cause
The `SessionPruningService` employed a fragile detection heuristic that used a broad `in` check against the entire `plan.md` content. This allowed emojis in non-status sections (like Rationales) to incorrectly flag a turn as "Non-Green". Additionally, the service lacked awareness of the turn currently being executed, causing a 1-turn lag where cleanup of a failed history only occurred once a *subsequent* turn was initiated.

### Proven Fix
1.  **Anchored Detection:** Implemented `_is_plan_green` using a regex (`r"^- \*\*Status:\*\*.*"`) to isolate the protocol-standard status line before checking for failure emojis.
2.  **Current Turn Awareness:** Expanded the `prune()` signature to accept `current_status: Optional[str]`. This allows the `SessionOrchestrator` to inject the status of the plan being reviewed (e.g., "SUCCESS 🟢"), triggering immediate cleanup of preceding failures.

### Systemic Prevention
- **Deliverable:** Refactor `extract_status_emoji` in `textual_plan_reviewer_helpers.py` to use the same anchored regex pattern as the pruning service. This deliverable has been added to Vertical Slice 00-04.
