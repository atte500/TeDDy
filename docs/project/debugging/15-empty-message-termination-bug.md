# Bug: Session Termination on Empty Message Does Not Trigger
- **Status:** Resolved
- **Milestone:** [Milestone 2: Stability & Infrastructure](/docs/project/milestones/02-stability-and-polish.md)
- **Vertical Slice:** N/A
- **Specs:** [Handoff Protocol](/docs/project/specs/handoff-protocol.md)

## Symptoms
**Expected:** When the user provides an empty reply to a `## Message` turn, the session should terminate immediately WITHOUT creating a `report.md` for that turn (as specified in Behavioral Rule #3 of the Handoff Protocol and the Milestone 2 Architecture Polish requirement).

**Actual:** The system returns "SUCCESS with no message" and continues the session instead of terminating.

**Minimal Reproduction Steps (to be refined):**
1. Start an interactive session (e.g., `teddy start -a debugger -m "Test message"`)
2. The agent generates a plan with a `## Message` block.
3. During the review phase, provide an empty reply (press enter with no text).
4. Expected: Session terminates, no `report.md` created.
5. Actual: "SUCCESS with no message" is returned and session continues.

## Context & Scope
### Regressing Delta
Incomplete implementation, not a specific commit. The empty-message termination logic was implemented as a guard in `SessionOrchestrator.execute()` (line 77: `if message is not None and not message.strip(): return None`). However, this guard is only triggered by the `message` parameter, which is used for the initial user message at `teddy start`. The user's reply to a `## Message` turn is captured by `ExecutionOrchestrator` after delivering the message, stored in `report.user_request` / `plan.metadata["user_request"]`, but never passed back as the `message` parameter to trigger the guard. The guard and the actual message-turn flow exist on different code paths.

### Environmental Triggers
- Interactive session mode (not manual `--yolo` mode)
- A turn that contains a `## Message` block (no actions)
- User providing an empty reply during the review phase
- Specifically: the empty reply path through `ExecutionOrchestrator`'s message turn handler

### Ruled Out
- The `SessionOrchestrator.execute()` guard itself (it works correctly when `message=""` is passed directly, as proven by the existing test)
- `PromptManager.resolve_message()` (returns `None` for whitespace-only, but that's for the initial message, not the reply to a message turn)

## Diagnostic Analysis
### Causal Model
The `SessionOrchestrator.execute()` method has a termination guard for empty messages, but it only applies to the `message` parameter (the initial user input). When a `## Message` turn is executed, the `ExecutionOrchestrator` handles the user interaction: it presents the message, then calls `user_interactor.ask_question()` to get the user's reply. This reply is stored in `report.user_request` but is **never** checked for emptiness to trigger session termination. Instead, execution continues normally: the report is written, turn transition happens, and the session continues. The missing link is: after executing a message turn, the system must check if the user's reply was empty and, if so, terminate the session without creating a report.md.

### Discrepancies
1. The Handoff Protocol specifies termination on empty reply without creating `report.md`, but actual behavior shows no termination and no crash. This suggests the empty reply check is either absent or ineffective. (Hypothesis: The check exists in `SessionOrchestrator.execute()` for the `message` parameter, but the empty user reply from a message turn does not flow through that check. Verification pending MRE execution.)

### Investigation History
1. Initial grep for "empty", "terminate session", "empty message", "empty reply" in `src/` failed due to interactive prompt detection in chained grep. Switched to single-pattern greps.
2. Read `session_orchestrator.py` and `prompt_manager.py`. Identified the termination guard at line 77 of orchestrator. Found existing test `test_session_orchestrator_empty_message.py` that validates this guard works when `message=""` is passed directly.
3. Read `session_lifecycle_manager.py` and `test_session_orchestrator_empty_message.py`. Confirmed the `resume()` method does NOT pass a `message` parameter to `execute()`. The empty user reply from a Message turn must come through a different path.
4. **Hypothesis:** The empty user reply is captured by `ExecutionOrchestrator` during message turn handling, stored in `report.user_request`, but never forwarded to the termination guard.
5. Read `execution_orchestrator.py` and confirmed that `report.user_request` is set from `plan.metadata["user_request"]` in `_handle_action_in_loop`. The metadata is set only when `captured_message` is truthy. Therefore, for empty replies, the metadata may not exist and the report user_request may be empty.
6. Read `action_executor.py` and `action_dispatcher.py`. Neither captures user reply for message actions; they dispatch the action which uses `user_interactor.ask_question()` directly (handled by the message action handler). The reply is stored in `plan.metadata["user_request"]` by `ExecutionOrchestrator._handle_action_in_loop` only if truthy.
7. **Diagnostic MRE + Shadow Verification:** Created `spikes/debug/15-empty-message-mre.py` and `spikes/debug/shadow_session_orchestrator.py`. The MRE tests three scenarios:
   - Test 1 (Production, buggy): Communication turn + empty user reply → did NOT terminate (FAIL) confirming the bug.
   - Test 2 (Shadow/fixed): Communication turn + empty user reply → terminated correctly (PASS) confirming the fix.
   - Test 3 (Shadow/fixed): Communication turn + non-empty reply → did NOT terminate (PASS) confirming no regression.
   **Root cause confirmed:** `SessionOrchestrator.execute()` lacks a check for `plan.metadata["user_request"]` / `report.user_request` after the inner orchestrator completes.
