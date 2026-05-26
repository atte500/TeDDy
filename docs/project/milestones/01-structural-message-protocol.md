# Milestone: 01-Structural Message Protocol

- **Status:** Planned
- **Specs:** [docs/project/specs/handoff-protocol.md](/docs/project/specs/handoff-protocol.md)

## Goal (The "Why")
To simplify the AI's communication by separating "acting" and "communicating" into mutually exclusive turn types, replacing the complex `PROMPT`, `INVOKE`, and `RETURN` actions with a structural `## Message` section.

## Proposed Solution (The "What")
We will implement the "Unified Turn" pattern, where the `MarkdownPlanParser` supports both `## Action Plan` and `## Message` headings. A `## Message` section is parsed into a specialized `MESSAGE` domain action that captures raw Markdown. The `ExecutionOrchestrator` will treat turns containing only a `MESSAGE` action as auto-executing communication turns.

## Guidelines (The "How")
- **Test Harness Triad:** Use `MarkdownPlanBuilder` to generate plans with the new `## Message` section and `ReportParser` to verify the resulting execution report.
- **Mutual Exclusivity:** Validation MUST fail if both `## Action Plan` and `## Message` are present in the same plan.
- **Transparency:** Deprecated legacy actions (`PROMPT`, `INVOKE`, `RETURN`) will trigger a terminal-only warning via `IUserInteractor` to encourage developer migration.

## Technical Specifications
- **New Action Type:** `MESSAGE`
- **Parser Rule:** `## Message` captures everything until EOF as `params["content"]`.
- **Orchestrator Rule:** If `plan.actions == [MESSAGE]`, skip approval and execute immediately.

## Vertical Slices
1. [01-01-parser-message-support.md](/docs/project/slices/01-01-parser-message-support.md): Parser expansion and mutual exclusivity validation.
2. 01-02-orchestrator-message-dispatch: Orchestrator support for the `MESSAGE` action and auto-execution. Implement warnings for deprecated legacy actions (`PROMPT`, `INVOKE`, `RETURN`).
3. 01-03-system-prompt-migration: Update all system prompts to the new protocol.
4. 01-04-legacy-deprecation: Removal of legacy actions.
