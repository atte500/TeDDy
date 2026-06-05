# Slice: 02-11-AST Parser Resilience

- **Status:** To De-risk
- **Type:** Feature
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [docs/project/specs/stability-and-bugfixes.md](/docs/project/specs/stability-and-bugfixes.md)
- **Component Docs:**
  - [MarkdownPlanParser](/docs/architecture/core/services/markdown_plan_parser.md)
  - [Parser Infrastructure](/docs/architecture/core/services/parser_infrastructure.md)

## Business Goal
Make the plan parser resilient to two common LLM formatting artifacts: (1) trailing text on the same line as a closing code fence (6+ backticks or tildes), which contaminates code block content, and (2) unexpected code blocks at the very end of a plan after all actions.

## Scenarios

> As a user, I want trailing text on the same line as a closing fence (e.g., `~~~~~~ trailing text`) to be stripped so that code block content is not contaminated with trailing fence text.
```gherkin
Given a plan whose last action's closing fence has trailing text on the same line
When the plan is parsed
Then the trailing text is stripped from the fence line
And the code block content does not contain the trailing text
```

> As a user, I want an unexpected code block at the end of the plan (after all valid actions) to be silently ignored so that LLM formatting noise doesn't cause a false validation failure.
```gherkin
Given a plan with valid actions followed by a trailing unclosed code block
When the plan is parsed
Then the trailing code block is silently ignored
And the correct actions from the valid part of the plan are returned
```

## Edge Cases
- **Same-line trailing text on OPENING fences**: Already handled by mistletoe (implicitly ignored). Double-cleaning by preprocessing causes no harm.
- **Same-line trailing text on 3/4/5-length fences**: These are not closing fences (length < 6), so they are NOT stripped. This is intentional — shorter fences are less likely to be LLM artifacts and more likely to be legitimate content.
- **Trailing Paragraph node (newline-separated trailing text)**: NOT handled in this slice. The user explicitly chose not to skip trailing Paragraph nodes — validation stays strict.
- **Trailing text inside a legitimate code block that happens to start with 6+ tildes**: This is an acceptable trade-off given the rarity of such content in plan files and the frequency of LLM noise.

## Deliverables
- [ ] **Harness** - Unit test: 6-backtick closing fence with same-line trailing text → stripped from CodeFence content.
- [ ] **Harness** - Unit test: 6-tilde closing fence with same-line trailing text → stripped.
- [ ] **Harness** - Unit test: trailing unexpected CodeFence at end of plan → silently ignored (existing BlockCode/CodeFence skip extended for tail-end).
- [ ] **Logic** - Implement `_FencePreProcessor.process()` to strip same-line trailing text on fence lines of 6+ backticks or tildes (strip trailing non-whitespace content after the fence characters on that line).
- [ ] **Logic** - Add tail-end skip in `_parse_actions` for trailing BlockCode/CodeFence nodes after the last action (consistent with 02-06's between-action skip pattern).
- [ ] **Wiring** - Acceptance test: plan with both same-line trailing text on closing fence AND trailing codeblock → SUCCESS with correct action content.

## Implementation Notes
(To be filled by the Developer as implementation proceeds.)

## Implementation Plan
### Changes Required

**File 1: `src/teddy_executor/core/services/parser_infrastructure.py`**
- Implement `_FencePreProcessor.process()` to scan each line. If a line (after optional leading whitespace) starts with 6+ consecutive backticks (`) or tildes (~) followed by non-whitespace content after the fence characters, strip the trailing content.

**File 2: `src/teddy_executor/core/services/markdown_plan_parser.py`**
- In `_parse_actions`, after the main while loop that consumes actions, add a tail-end loop that silently consumes any remaining `BlockCode` or `CodeFence` nodes (but NOT `Paragraph`).

### Test Strategy (Test Harness Triad)
- **Driver**: Use `MarkdownPlanBuilder` for constructing valid plans, then append trailing artifacts via raw string manipulation.
- **Observer**: Use standard `pytest` assertions on the parsed `Plan` object (action count, action content).
- **Setup**: Standard `parser` fixture from `conftest.py` resolving `IPlanParser`.
