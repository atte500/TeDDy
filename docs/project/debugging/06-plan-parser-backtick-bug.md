# Bug: Plan Parser Backtick Interference
- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](/docs/project/milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** N/A
- **Specs:** [plan-format.md](/docs/project/specs/plan-format.md)

## Symptoms
The plan parser fails when an action's parameter list contains backticks (inline code).
The error report indicates an unexpected `Code Block (indented)` is found instead of a Level 3 Heading.

## Context & Scope
### Regressing Delta
Unknown. Likely in `MarkdownPlanParser` or `ActionParserStrategies`.

### Environmental Triggers
Markdown plans with `- **Key:** `value`` format in action lists.

### Ruled Out
- TBD

## Diagnostic Analysis
### Causal Model
1. **Trigger:** A Level 3 Action Heading is followed by a List where one or more items contain backticks.
2. **AST Generation:** `mistletoe` parses the Markdown.
3. **Consumption:** The specific action parser (e.g., `parse_read_action`) is called.
4. **Failure:** The parser fails to fully consume the List or misinterprets the AST, leaving trailing nodes that the main loop in `_parse_actions` cannot handle.

### Discrepancies
- User reports backticks are the trigger (resolved: backticks don't change AST; trailing spaces do).
- `_parse_actions` was intolerant of inter-action junk nodes (resolved: implemented surgical resilience for whitespace-only BlockCode nodes).

## Solution
### Implemented Fixes
- Modified `MarkdownPlanParser._parse_actions` to skip `BlockCode` nodes that contain only whitespace. This resolves the failure triggered by trailing indented spaces (which are common when AI or users include backticks in list items).
- Maintained strict validation for "meaningful" non-heading nodes (Paragraphs, ThematicBreaks) to ensure structural integrity and passing state of existing error tests.

### Prevention
- Added `tests/suites/unit/core/services/test_parser_resilience.py` to ensure the parser remains resilient to whitespace-only code blocks between actions.

### Investigation History
- [2026-04-28]: Case File created based on user report.
- [2026-04-28]: Verified AST behavior via `repro_backtick.py`. Backticks do not change AST; 4+ spaces create `BlockCode`.
- [2026-04-28]: Confirmed "Strict Orchestration" bug when the executor itself failed to parse the Debugger's plan because it contained the reproduction case (10 spaces of indentation).
