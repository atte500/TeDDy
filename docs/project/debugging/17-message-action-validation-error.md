# Bug: MESSAGE Action Type Validation Error Message
- **Status:** Resolved
- **Milestone:** [N/A]
- **Vertical Slice:** [N/A]
- **Specs:** [N/A]

## Symptoms
When an agent includes `### MESSAGE` (or `### Message`) as an action block under `## Action Plan`, the validator outputs "Unknown action type: MESSAGE" instead of a clearer error message such as "Plan cannot contain Message in action turn. Mutual exclusivity is required."

**Expected Behavior:** The validator should recognize that MESSAGE is not a valid action type because `## Message` is a mutually exclusive alternative to `## Action Plan`. The error should guide the user/agent to use `## Message` instead of `### Message` or remove the section.

**Actual Behavior:** The validator treats `MESSAGE` as an unknown action type and says "Unknown action type: MESSAGE".

## Context & Scope
### Regressing Delta
[To be determined during investigation]

### Environmental Triggers
Triggered whenever a plan contains a `### MESSAGE` heading under `## Action Plan`.

### Ruled Out
[N/A]

## Diagnostic Analysis
### Causal Model
The `MarkdownPlanParser._parse_actions` method uses a dispatch map (`_dispatch_map`) with keys: CREATE, READ, EDIT, EXECUTE, RESEARCH. When an agent writes `### MESSAGE` under `## Action Plan`, the parser extracts the action type string ("MESSAGE"), fails to find it in `_dispatch_map`, and falls through to the generic error: `f"Unknown action type: {action_type_str}"`. Similarly, `PlanValidator.validate` has a fallthrough `else` clause after checking for `research`, `prompt`, `invoke`, `return` which emits `f"Unknown action type: {action.type}"`.

The mutual exclusivity check at the H2 level (in `_parse_strict_top_level`) only catches when both `## Action Plan` and `## Message` headings coexist. It does **not** intercept a `### MESSAGE` heading **nested inside** `## Action Plan`. This is the discrepancy: the system has a mutual exclusivity rule (plan cannot contain both sections), but the parser/validator do not handle the case where `MESSAGE` appears as an action within `## Action Plan`.

### Discrepancies
- The mutual exclusivity check at H2 level works (detects both `## Action Plan` and `## Message`), but `### MESSAGE` under `## Action Plan` is not caught by this check, falling through to the generic "Unknown action type" error. (Resolved: This is the root cause. The parser and validator need explicit `MESSAGE` checks before the generic fallthrough.)

### Investigation History
1. **Initial MRE** (`spikes/debug/17-message-mre.py`): Parsed a plan with `### MESSAGE` under `## Action Plan`. Output: `BUG CONFIRMED: Got 'Unknown action type' error instead of mutual exclusivity hint.` Concluded: The parser does not handle `MESSAGE` as a known action type.
2. **Shadow parser fix** (`spikes/debug/shadow_markdown_plan_parser.py`): Added a guard in `_parse_actions` before the generic fallthrough to raise a specific mutual exclusivity error.
3. **Shadow MRE** (`spikes/debug/test_shadow_mre.py`): Imported the shadow parser and executed. Output: `FIX VERIFIED: Shadow parser correctly raises mutual exclusivity error.` Concluded: The fix is correct and produces a clear mutual exclusivity error.
4. **Systemic Audit** (`git grep "Unknown action type"`): Found 4 source locations:
   - `markdown_plan_parser.py:251` — generic error in `_parse_actions` (target for fix).
   - `plan_validator.py:69` — generic error in `validate` (target for fix).
   - `action_factory.py:137` — runtime ValueError (out of scope for plan validation, but noted).
   - `tests/` files — test assertions that will need updating if error message changes.

## Solution
### Root Cause
The parser (`_parse_actions`) and validator (`validate`) both have generic fallthrough clauses that emit "Unknown action type: MESSAGE" when encountering a `### MESSAGE` heading under `## Action Plan`. The mutual exclusivity check only works at the H2 level.

### Fix
1. **Parser (`markdown_plan_parser.py`)**: In `_parse_actions`, before the generic fallthrough `if action_type_str not in self._dispatch_map:`, add an explicit check for `action_type_str == "MESSAGE"` that raises `InvalidPlanError` with a message explaining mutual exclusivity.
2. **Validator (`plan_validator.py`)**: In `validate`, before the `else` fallthrough clause that produces "Unknown action type", add an explicit check for `action_type_lower == "message"` that appends a `ValidationError` with a mutual exclusivity message.

### Preventative Measures
- Add "MESSAGE" to the validator's fallthrough list (e.g., `["research", "prompt", "invoke", "return", "message"]`) to prevent future generic errors for this action type.
- Update integration tests that assert on the current "Unknown action type" error message to expect the new mutual exclusivity message.
- The `action_factory.py` instance is out of scope; it handles runtime execution, not plan validation.
