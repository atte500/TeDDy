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
- **CLI Flag Realignment:** Support `-a/--agent` and `-c/--context` on the `start` command to allow programmatic handoffs via prompt instructions.

## Technical Specifications
- **New Action Type:** `MESSAGE`
- **Parser Rule:** `## Message` captures everything until EOF as `params["content"]`.
- **Orchestrator Rule:** If `plan.actions == [MESSAGE]`, skip approval and execute immediately.
- **Legacy Pruning:** Deprecated legacy actions (`PROMPT`, `INVOKE`, `RETURN`) MUST be removed from `ActionType` and the parser's dispatch map.

## Vertical Slices
1. [01-01-parser-message-support.md](/docs/project/slices/01-01-parser-message-support.md): Parser expansion and mutual exclusivity validation. (Completed)
2. [01-02-orchestrator-message-dispatch.md](/docs/project/slices/01-02-orchestrator-message-dispatch.md): Orchestrator support for the `MESSAGE` action and auto-execution. (Completed)
3. [01-03-cli-flag-realignment.md](/docs/project/slices/01-03-cli-flag-realignment.md): Implement `-a`, `-m`, `-c` and LLM overrides on the `start` command. (Planned)
4. [01-04-system-prompt-migration.md](/docs/project/slices/01-04-system-prompt-migration.md): Update all 6 default system prompts to the new protocol. (Completed)
5. [01-05-legacy-deprecation.md](/docs/project/slices/01-05-legacy-deprecation.md): Removal of legacy actions from the domain and parser. (Planned)
