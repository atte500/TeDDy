# Spec: Structural Message Protocol

## 1. Overview
This protocol replaces the `PROMPT`, `INVOKE`, and `RETURN` actions with a structural convention in the Markdown Plan Format. This simplifies the AI's task by treating "acting" and "communicating" as mutually exclusive turn types.

## 2. Structure
A plan file must contain either an `## Action Plan` OR a `## Message` section following the `## Rationale`.

### 2.1. Acting Turns (`## Action Plan`)
Used when the agent needs to perform file system, shell, or research operations.
- The presence of `## Action Plan` signals the executor to parse and present actions for approval.
- A handoff to the `User` is implicit upon completion of the actions.

### 2.2. Communicating Turns (`## Message`)
Used when the agent needs to talk to the user, hand off to another agent, or signal completion.
- Everything following the `## Message` header is treated as raw Markdown content for the recipient.
- There are no formal parameters like `Target` or `Reference Files`.
- **Reference Files:** Should be included as standard Markdown links within the body of the message (e.g., `Check the logs in [report.md](/path/to/report.md)`).
- **Handoffs:** To hand off to another agent, the message should include the specific CLI instruction for the user to start a new session (e.g., `teddy start -a developer ...`).

## 3. Behavioral Rules
1. **Isolation:** A plan cannot contain both `## Action Plan` and `## Message`. If both are present, validation fails.
2. **Implicit Target:** All `## Message` blocks are presented to the User.
3. **Completion:** If the message signals completion and the user provides an empty response, the session terminates.
