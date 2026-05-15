# Bug: Session Loop Breakage on Prompt and Failure
- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** [00-04-context-management-ui.md](../slices/00-04-context-management-ui.md)
- **Specs:** [interactive-session-workflow.md](../specs/interactive-session-workflow.md)

## Symptoms
1. Replying to `PROMPT` action with `-y` (auto-approval) breaks out of the session loop.
2. `EXECUTE` action failure prompts for "Enter your instructions for the AI" instead of proceeding to generate an execution report and continuing the loop.
3. Resuming a session on a failed execution report prompts for instructions instead of automatically reading the report and planning the next turn.

## Context & Scope
### Regressing Delta
TBD - Likely in `SessionOrchestrator` or `ExecutionOrchestrator` logic refactored in Slice 8/9.

### Environmental Triggers
- Interactive session mode.
- Use of `PROMPT` action.
- `EXECUTE` action returning non-zero exit code.

### Ruled Out
TBD

## Diagnostic Analysis
### Causal Model
1. **Turn Execution:** When a plan is executed, action results are captured in `ActionLog`s.
2. **PROMPT Action:** If a `PROMPT` action occurs, the user's response is stored in `log.details["response"]`.
3. **Turn Finalization:** `SessionOrchestrator` finalizes the turn, creating a `report.md`.
4. **Resumption/Planning:** When the next turn begins, `SessionPlanner._resolve_message_from_previous_turn` looks at the previous report.
5. **Success Branch:** If status was `SUCCESS`, it returns `""`. `PromptManager` treats `""` as "continue", but the LLM receives an empty message, losing the context of the `PROMPT` response (which is buried in the action log).
6. **Failure Branch:** If status was `FAILURE`, it extracts the `User Request` section using `extract_markdown_section`. If the header level in the template doesn't match the planner's expectation (Level 2), it returns `None`.
7. **Manual Fallback:** `PromptManager.resolve_message` falls back to `ask_question` when the message is `None`.

### Discrepancies
- **Loop continues on SUCCESS but with empty message.** Conflict: Expected to automatically use the `PROMPT` response as the instruction for the next turn. (Resolved: This is INTENDED behavior. The `PROMPT` response exists in the audit trail (previous report) and does not need to be duplicated in the next turn's `User Request` section. Returning `""` correctly signals continuation).
- **Loop prompts user on FAILURE.** Conflict: Expected to automatically continue based on the audit trail. (Resolved: The planner returned `None` if it couldn't find a `User Request` section in a failure report. This triggered the manual prompt fallback in `PromptManager`. Returning `""` as a default fallback whenever a report exists ensures the loop stays alive).

### Investigation History
1. Initial report: Session loop breaks on `PROMPT` and `EXECUTE` failure.
2. Repro verified: `SUCCESS` returns `""` and `FAILURE` triggers manual prompt if extraction fails.
3. Systemic Audit: Identified duplicate brittle extraction logic in `PromptManager`.
4. Verification: Proven that returning `""` (continuation) when a report exists maintains the loop without context loss or manual prompts.

## Solution
### Root Cause
The session loop was breaking because `SessionPlanner` and `PromptManager` relied on brittle markdown extraction logic that only looked for Level 2 `## User Request` headers. If a turn failed and the section was missing (which it is after Turn 1), the planner returned `None`, triggering a manual fallback prompt in `PromptManager`.

### Proven Fix (Audit Trail Principle)
The system now treats the presence of a previous report as a sufficient signal to continue the session loop automatically.
- **Continuation by Default:** `SessionPlanner` now returns `""` (continuation signal) whenever a previous turn's `report.md` exists. This ensures the AI continues using the existing audit trail as context.
- **Explicit Instruction Promotion:** The system still searches for a `User Request` section in the previous report to support cases where the user provided a fresh instruction (via initial start or the TUI's 'm' key) that should be promoted for exactly one turn.
- **No Redundancy:** `PROMPT` responses are not forwarded across turns; they live in the history, and the AI is expected to read them from its context.

### Systemic Prevention
- Centralize instruction resolution into a robust helper in `markdown.py` that implements the "Audit Trail" priority: `Explicit User Request` -> `Continuation Signal ("")` if report exists -> `Manual Prompt` (None).
- Eliminate the duplicated brittle extraction logic in `SessionPlanner` and `PromptManager`.
