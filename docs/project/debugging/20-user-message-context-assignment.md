# Bug: User Additional Request Turn Saved to turn.context Instead of session.context
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
**Expected:** When a user provides an additional request during review and `preserve_message_turns: true` is configured, the turn should be saved to `session.context` instead of `turn.context`.

**Actual:** The turn is saved to `turn.context` regardless of the `preserve_message_turns` setting.

**Reproduction Steps:**
1. Start a session with `preserve_message_turns: true` in config
2. During a turn review, provide an additional message/request (via 'm' key or message reply)
3. The turn's artifacts (plan.md, report.md) are added to `turn.context` instead of `session.context`

## Context & Scope
### Regressing Delta
The bug was introduced in Milestone 2, Slice 02-10 (Preserve User-Message Turns). The implementation used `- **User Request:**` as the detection pattern for user-request turns in both `_is_preserved_turn` and `_check_report_has_user_request`, but the actual report template (`execution_report.md.j2`) renders the user request as `## User Request` (heading format). This mismatch means the detection NEVER matches, so user-request turns are never added to `session.context` — they fall through to the default `turn.context` path.

### Environmental Triggers
- Requires `preserve_message_turns: true` in config.yaml (the default)
- Requires a user to provide an additional message during turn review (via 'm' key or message reply)

### Ruled Out
- The `## Message` detection for message turns works correctly (both the plan header and regex use `## Message`)
- The report generation and template rendering work correctly (the `## User Request` heading is properly output)
- The `transition_to_next_turn` logic in `session_service.py` correctly calls `_is_preserved_turn` and routes to `session.context` — the detection itself fails

## Diagnostic Analysis
### Causal Model
The system has two detection functions that check if a turn is a "user-request turn":
1. `SessionService._is_preserved_turn()` — called during turn transition to decide whether to append to `session.context` or `turn.context`
2. `SessionPruningService._check_report_has_user_request()` — called during pruning to spare user-request turns from auto-pruning

Both functions use the regex pattern `^- \*\*User Request:\*\*` (bullet format) to detect user-request turns.

However, the Jinja2 report template (`execution_report.md.j2`) renders the user request as:
```markdown
## User Request
```text
[content]
```
```

This is a Markdown heading (`## User Request`), not a bullet list item (`- **User Request:**`). The bullet format is NOT included anywhere in the template output.

Therefore, BOTH detection functions always return `False` for any real report file containing a user request. This causes:
1. User-request turns to be appended to `turn.context` instead of `session.context`
2. User-request turns to be eligible for auto-pruning (they are not spared)

### Discrepancies
- `_is_preserved_turn` regex `^- \*\*User Request:\*\*` vs actual template output `## User Request` (resolved: regex must be changed to `^## User Request`)
- `_check_report_has_user_request` regex `^- \*\*User Request:\*\*` vs actual template output `## User Request` (resolved: same fix needed)
- `test_session_pruning_preserve_user_requests.py` tests use bullet format in mock data, which would pass detection with the buggy regex but fail to represent real reports (resolved: test mocks must be updated to match the actual heading format)

### Investigation History
1. Traced `user_request` data flow: `plan.metadata["user_request"]` → `ExecutionReport.user_request` → template renders `## User Request` heading. Detection checks for `- **User Request:**` bullet. ROOT CAUSE: format mismatch.
2. MRE (`20-mre-context-assignment.py`): Proved that buggy detection returns False for actual template output (heading format) and fixed detection returns True.
3. Comprehensive MRE (`20-mre-comprehensive.py`): Confirmed both detection methods (`_is_preserved_turn` and `_check_report_has_user_request`) have the same bug. 7/8 tests pass, 1 FAIL (the buggy test expected to detect heading format but failed — confirming the bug).
4. Systemic audit: `git grep` found ONLY the two locations with the buggy regex. No other occurrences in the codebase.

## Solution
### Root Cause
A regex string mismatch between the detection pattern (`- **User Request:**` — bullet list item format) and the actual template output (`## User Request` — heading format) in two locations:
1. `session_service.py:_is_preserved_turn()` — line with `r"^- \*\*User Request:\*\*"`
2. `session_pruning_service.py:_check_report_has_user_request()` — line with `r"^- \*\*User Request:\*\*"`

### Fix
Change the regex in both locations from:
```python
r"^- \*\*User Request:\*\*"
```
to:
```python
r"^## User Request"
```

### Preventative Measures
This is a class of bug where a detection pattern hardcoded in the application does not match the actual output of a template. To prevent this globally:
1. **Template Constant Enforcement:** Define the detection patterns as constants alongside the template that produces them. For example, in the Jinja2 template, include a comment that documents the exact format expected by the detection logic, and in the Python code, import a shared constant rather than hardcoding the regex.
2. **Cross-reference Test:** Write a test that renders a report from known data, then verifies that the detection functions correctly identify the rendered output. This would have caught this bug immediately.
3. **Review existing tests:** The tests in `test_session_pruning_preserve_user_requests.py` use mock data with the bullet format (`- **User Request:**`), which passes the buggy regex but does not reflect real template output. Tests should use data that matches the actual template output.
