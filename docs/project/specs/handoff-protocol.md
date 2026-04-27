# Spec: Unified HANDOFF Protocol

## 1. Overview
Replaces the `PROMPT`, `INVOKE`, and `RETURN` actions with a single, universal `HANDOFF` action. This unifies the turnover logic and simplifies the instructions provided to AI agents.

## 2. Format
The `HANDOFF` action supports a metadata list for parameters and free-form Markdown for the message content.

```markdown
### `HANDOFF`
- **Target:** [Agent Name | User | none] (Optional: Empty defaults to 'none')
- **Reference Files:** (Optional)
  [path/to/file](/path/to/file)

[Free-form Markdown message content here]
```

## 3. Parameter Logic
- **Target**: Defines the recipient of the handoff.
    - `User`: Hands control back to the human (default for top-level agents).
    - `[Agent Name]`: Invokes a specialist agent (e.g., `Architect`).
    - `none` (or empty): Signals that the current agent has completed its sub-task. The system automatically resolves the recipient by popping the "Calling Agent" (Parent) from the session's call stack.
- **Reference Files**: A list of root-relative links to be added to the recipient's context for the next turn.

## 4. Behavioral Transitions
- **The Call Stack**: To support the `none` target, the session metadata (`meta.yaml`) must maintain an "Agent Stack" (LIFO).
    - Specifying an `[Agent Name]` pushes that agent onto the stack.
    - Specifying `none` pops the current agent and restores the previous one.
- **Auto-Approval**: If the plan contains ONLY a `HANDOFF`, it bypasses the TUI review for fluid conversation.
- **Isolation**: A `HANDOFF` action MUST be the only action in a plan (otherwise it's skipped / deselected by default).
