# Slice: Session Auto-Naming Refinement

- **Status:** Completed
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Specs:** [interactive-session-workflow](../specs/interactive-session-workflow.md)

## Business Goal
Improve the professional quality and reliability of auto-generated session names by implementing a robust "Clean & Truncate" string manipulation utility. This ensures session folders are easy to navigate and compatible with all filesystems.

## Scenarios
> As a user, when I start a session without a name, I want the session folder to be automatically named based on my first plan's title, but cleaned of special characters and truncated to a readable length.

```gherkin
Given a plan title "Refactor: Authentication Service (v2) - Security Fixes!!!"
When the session is auto-named
Then the session folder name should be "refactor-authentication-service-v2-security-fixes"
And it should be truncated if it exceeds 50 characters without leaving trailing hyphens.
```

## Deliverables
- [x] Logic - Implement `slugify` utility with Clean & Truncate logic in `src/teddy_executor/core/utils/string.py`.
- [x] Logic - Update `SessionPlanner._handle_dynamic_rename` and `SessionService.create_session` to use the new utility.
- [x] Refactor - Remove redundant regex logic from `SessionPlanner`.

## Delta Analysis
- **Modify:** `src/teddy_executor/core/services/session_planner.py` to replace inline regex with utility.
- **Add/Modify:** `src/teddy_executor/core/utils/markdown.py` (or a new `string.py` if more appropriate) to host the `slugify` logic.

## Guidelines for Implementation
- **Clean:** Lowercase, replace non-alphanumeric with `-`, collapse `--` to `-`, strip leading/trailing `-`.
- **Truncate:** Max 50 characters. Try to avoid breaking words if easy, but prioritize the character limit.
- **Test Harness:** Unit tests in `tests/suites/unit/core/utils/test_markdown_utils.py` (or similar).

## Implementation Notes
