# Bug: Validation error message recorded in meta.yaml as user request
- **Status:** Resolved
- **Milestone:** [/docs/project/milestones/10-interactive-session-and-config.md](/docs/project/milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** [/docs/project/slices/00-07-validation-error-meta-user-request.md](/docs/project/slices/00-07-validation-error-meta-user-request.md)
- **Specs:** [Interactive Session Specification](/docs/project/specs/interactive-session-workflow.md)

## Symptoms
When a plan fails validation during a stateful session turn:
1. The `SessionReplanner` triggers an automated re-plan loop.
2. It generates a detailed feedback message (containing validation errors, the AST, and original plan content) to pass back to the LLM.
3. It calls `PlanningService.generate_plan(user_message=feedback, ...)` to generate the corrected plan.
4. `PlanningService` captures this automated feedback message as the `user_request` in `meta.yaml` of the new turn, overwriting or standing in place of the actual user request.

Expected:
- The actual user request (the original intent of the session turn) or an appropriate indicator of the replan sequence should be preserved or handled correctly.
- Automated validation feedback messages MUST NOT be recorded as the user's manual prompt (`user_request`) in `meta.yaml`.

## Context & Scope

### Regressing Delta
- **Files altered:** `src/teddy_executor/core/services/planning_service.py` and `src/teddy_executor/core/services/session_replanner.py`.
- **Detail:** `PlanningService.generate_plan` resolves `user_message` using `self._prompt_manager.resolve_message` and directly maps it to `meta["user_request"]`. However, during a validation failure replan, `user_message` is not a standard user intent message, but rather an automated feedback payload.

### Environmental Triggers
- Reproducible in both interactive and non-interactive sessions whenever a plan fails physical/logical validation checks.

### Ruled Out
- `MarkdownPlanParser`, `LocalFileSystemAdapter`, and outer CLI options are unrelated to this metadata assignment.

## Diagnostic Analysis

### Causal Model
1. Validation fails in `SessionOrchestrator._validate_plan_with_context`.
2. `SessionOrchestrator._handle_logical_validation_errors` triggers the lifecycle manager replan via `self._lifecycle_manager.trigger_replan`.
3. `SessionLifecycleManager.trigger_replan` invokes `SessionReplanner.trigger_replan_turn`.
4. `SessionReplanner.trigger_replan_turn` formats a rich validation feedback message containing errors and original faulty content.
5. `SessionReplanner.trigger_replan_turn` calls `self._planning_service.generate_plan` passing this feedback string as `user_message`.
6. `PlanningService.generate_plan` processes `user_message` through `self._prompt_manager.resolve_message`.
7. `PlanningService.generate_plan` unconditionally stores the resolved message in `meta["user_request"]`. (This is the failure point: it does not distinguish standard manual planning from automated validation replan planning.)
8. `PromptManager.update_meta` serializes `meta` into the next turn's `meta.yaml`.
9. The automated validation feedback message is written as `user_request` in the `meta.yaml` of the new turn, overwriting the user's actual original instruction.

### Discrepancies
- Automated feedback message treated as human `user_request` inside `meta.yaml`. Conflict: Contradicts the design that `user_request` represents the human's guiding prompt or intention for the session. (Resolved: Our fix propagates the `is_replan: True` flag to `meta.yaml` during transition on validation failures, which allows `PlanningService` to avoid overwriting `user_request` with the automated validation feedback message, preserving the parent turn's manual request instead.)

### Investigation History
1. Grepped for `meta.yaml` to trace where metadata writes occur.
2. Grepped for `user_request` to locate state-mutation points.
3. Read `SessionOrchestrator`, `SessionLifecycleManager`, `SessionReplanner`, and `PlanningService` to trace the call graph during automatic replanning. Verified that automated feedback is passed directly as `user_message` and stored unconditionally as `user_request`.
4. Created a Minimal Reproducible Example (MRE) in `spikes/debug/01-validation-error-meta-user-request-mre.py` and successfully reproduced the bug with code status exit code 1.
5. Built a sandboxed fix in `spikes/debug/shadow_session_service.py` and `spikes/debug/shadow_planning_service.py` using Shadow Files to introduce the `is_replan` state propagation and prevent `user_request` overwrites.
6. Ran the MRE targeting the shadow files and confirmed it passed with exit code 0, proving the fix.

## Solution

### Root Cause
During plan validation failures in a stateful session turn, `SessionReplanner` triggers an automated re-plan loop and generates an automated validation feedback message containing errors and AST representations. This feedback message is passed to `PlanningService.generate_plan(user_message=feedback, ...)` to request a corrected plan.
However, because `PlanningService` did not differentiate standard manual user prompts from automated feedback messages, it unconditionally set `meta["user_request"] = resolved_message`, resulting in the automated feedback overwriting the actual user's original request in the next turn's `meta.yaml`.

### Proven Fix
1. **Transition State Propagation:** In `SessionService.transition_to_next_turn` (when `is_validation_failure` is True), we set an `is_replan: True` flag in the next turn's metadata and carry forward the previous turn's `user_request`.
2. **Metadata Overwrite Protection:** In `PlanningService.generate_plan`, we check if `meta.get("is_replan")` is True. If so, we suppress writing `user_request` with the automated validation feedback message, preserving the parent turn's manual instruction instead.

### Systemic Prevention
- **Avoid Mixing Channels:** In stateful multi-turn agent protocols, keep automated loopback feedback/evaluation channels strictly separated from human instruction state.
- **Explicit Turn Metadata Flags:** Propagate explicit loop flags (such as `is_replan`, `is_retry`, `agent_invocation`) in session metadata so core services can robustly adapt state-mutation behaviors without fragile string-matching or assumption-heavy logic.
