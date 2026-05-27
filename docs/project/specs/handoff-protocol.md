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
- **User as Mediator:** All `## Message` blocks are presented to the User. The User acts as the bridge for all agent handoffs.
- **Structure:** Free-form Markdown content. No formal parameters (like `Target` or `Reference Files`).
- **Reference Files:** MUST be included as root-relative Markdown links within the message body (e.g., `[report.md](/path/to/report.md)`).
- **Handoffs:** To delegate to another agent, the message MUST provide clear instructions and the exact CLI command for the user to run (e.g., `teddy start -a developer -m "Implement this slice" -c "path/to/slice.md"`).

## 3. Behavioral Rules
1. **Isolation:** A plan cannot contain both `## Action Plan` and `## Message`. If both are present, validation fails.
2. **Implicit Target:** All `## Message` blocks are presented to the User.
3. **Completion:** If the user provides an empty response, the session terminates.
