# Bug: Action Name Symbol Tolerance
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
When a plan contains an action heading with trailing symbols (e.g., `### `READ**` instead of `### `READ``), the parser fails to recognize it as a valid action. Expected: the parser should strip non-alphabetic symbols from the action name before matching, so `### `READ**` is treated identically to `### `READ``.

## Context & Scope

### Regressing Delta
Initial request – not yet identified. Likely the action name extraction logic in the parser.

### Environmental Triggers
Any plan with action headings that contain stray punctuation after the action name.

### Ruled Out
N/A

## Diagnostic Analysis

### Causal Model
The `get_action_heading` function in `parser_infrastructure.py` extracts the action type from an H3 heading's text using `text.split(":")[0].strip().replace("`", "")`. For `### `READ**`, this yields `"READ**"`, which is not in `valid_actions`. The fallback that accepts any H3 whose first child is `InlineCode` also fails because mistletoe parses the unclosed backtick sequence as `RawText`, not `InlineCode`. Thus `get_action_heading` returns `None`, causing `_parse_actions` to raise "Plan content is invalid: a Level 3 Action Heading."

The root cause is that `potential_type` is not normalized to strip non-alphabetic symbols before the `valid_actions` membership check. Adding `cleaned_type = re.sub(r'[^A-Za-z]', '', potential_type)` before the `in valid_actions` check resolves the issue.

### Discrepancies
- The MRE expected "Unknown action type: READ**" error but got "Plan content is invalid: a Level 3 Action Heading." (resolved: The failure occurs earlier in `get_action_heading`, not at dispatch map lookup. The heading is never recognized as a valid action, so `_parse_actions` never reaches the dispatch lookup.)

### Investigation History
1. **Hypothesis: `### `READ**` fails at dispatch map lookup.** Observation: The MRE raised "Plan content is invalid: a Level 3 Action Heading" instead. Conclusion: The failure is at the heading recognition level, not dispatch.
2. **Hypothesis: The heading is not recognized as an H3.** Observation: AST probe confirmed the node IS an H3 heading, but its child is `RawText` (content='`READ**'), not `InlineCode`. Conclusion: The `InlineCode` fallback in `get_action_heading` fails because mistletoe does not produce `InlineCode` tokens for unclosed backtick sequences.
3. **Hypothesis: Normalizing `potential_type` by stripping non-alpha characters will make `get_action_heading` accept the heading.** Observation: Pending verification via shadow file.

## Solution
The root cause was that action type strings extracted from H3 headings were not normalized to strip non-alphabetic characters before comparison against `valid_actions` (in `get_action_heading`) and `_dispatch_map` (in `_parse_actions`). When a heading like `### `READ**` was parsed, the raw string `"READ**"` failed both checks.

**Proven Fix (shadow file verified):** In `get_action_heading`, add `cleaned_type = re.sub(r'[^A-Za-z]', '', potential_type)` before the `in valid_actions` check. In `_parse_actions`, apply the same normalization to `action_type_str` before the `in self._dispatch_map` check.

**Preventative Measures:** This class of bug ("unchecked/unnormalized string comparison where user-provided text with stray symbols is compared against a known set") is isolated to these two locations in the parser. No other `valid_actions` or `_dispatch_map` comparisons exist in the codebase. The fix uses `re.sub(r'[^A-Za-z]', '', ...)` which strips all non-alphabetic characters, making the parser tolerant of any stray symbols (asterisks, underscores, etc.) in action names.
