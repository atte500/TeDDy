# Slice: 01-01-Parser Message Support

- **Status:** Planned
- **Milestone:** [docs/project/milestones/01-structural-message-protocol.md](/docs/project/milestones/01-structural-message-protocol.md)
- **Specs:** [docs/project/specs/handoff-protocol.md](/docs/project/specs/handoff-protocol.md), [docs/project/specs/plan-format.md](/docs/project/specs/plan-format.md)
- **Component Docs:** [docs/architecture/core/services/markdown_plan_parser.md](/docs/architecture/core/services/markdown_plan_parser.md)

## Business Goal
Update the `MarkdownPlanParser` to recognize the `## Message` section as a valid alternative to `## Action Plan`, allowing agents to communicate without using complex action syntax.

## Scenarios
> As an Agent, I want to send a plain Markdown message to the user using a dedicated heading so that I don't have to wrap my response in a `PROMPT` action.

```gherkin
Given a plan containing a "## Message" section
When the plan is parsed
Then a Plan object is returned containing exactly one "MESSAGE" action
And the action parameters contain the raw Markdown content from the Message section
```

> As a Developer, I want the parser to enforce mutual exclusivity between messages and actions to prevent ambiguous turn intent.

```gherkin
Given a plan containing both "## Action Plan" and "## Message"
When the plan is parsed
Then an "InvalidPlanError" is raised detailing the mutual exclusivity violation
```

## Edge Cases
- **Empty Message**: If the `## Message` section is empty, then the plan should still be valid with an empty message content, in order to allow for minimal signaling.
- **Nested Headings in Message**: If the message contains Level 3+ headings, then they should be treated as part of the message content, in order to preserve the intended Markdown structure.
- **Trailing Junk**: If there is text or headings *after* the `## Message` section content, then it should all be included in the message content until EOF, because `## Message` is a terminal section.

## Deliverables
- [ ] **Contract** - Add `MESSAGE` to `ActionType` enum in `src/teddy_executor/core/domain/models/plan.py`.
- [ ] **Logic** - Update `MarkdownPlanParser._parse_strict_top_level` to handle the bifurcated path (Action Plan vs Message).
- [ ] **Logic** - Implement `parse_message_action` to capture all remaining AST nodes until the end of the document.
- [ ] **Seam** - Update `ActionFactory` to map `MESSAGE` to a new internal handler (or the user interactor).
- [ ] **Wiring** - Ensure the `MESSAGE` action is correctly integrated into the `Plan` object returned by the parser.

## Implementation Plan
1. Update `ActionType` enum.
2. Modify `MarkdownPlanParser.parse` to detect which section is present after the Rationale.
3. If `## Message` is detected, consume all remaining nodes and render them back to Markdown for the action `params`.
4. Add structural validation to ensure only one of the two sections exists.
5. Add unit tests in `tests/suites/unit/core/services/test_parser_message_protocol.py`.
