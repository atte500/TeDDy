# Task: Fix Report & TUI Display of READ/EXECUTE Parameters

## Business Goal
Polish three UX issues: (1) remove spurious "Metadata Used File Path Alias" from execution reports, (2) prevent READ with Lines from polluting the next turn's context while still displaying the line-range content in the report, and (3) show Lines/Tail parameters in the TUI right panel.

## Context

### Issue 1: "Metadata Used File Path Alias" in Report
The key `"Metadata Used File Path Alias"` (value `True`) is an internal plumbing key added to `action.params` during READ execution. The Jinja2 template's generic params loop (`execution_report.md.j2`, ~line 236-250) iterates all params and renders any key not in the `ignored` list. This key is not in the ignored list, so it renders as `- **Metadata Used File Path Alias:** True`.

**Fix:** Add `'metadata used file path alias'` (lowercase, as the template normalizes keys) to the `param_ns.ignored` namespace list.

### Issue 2: READ Lines Context Pollution + Missing Content Display
READ actions with `Lines` specified should NOT add the file path to the next turn's `turn.context` (preventing full-file pollution in `input.md`). However, the line-range content must still be visible to the agent. Currently, in session mode, resource contents are suppressed from the report. The line-range content currently disappears from both the report AND the next turn's input.md.

**Fix (2A):** In the Turn Transition Algorithm's "Apply Standard Context Changes" step (where READ/CREATE/EDIT paths are added to `T_next/turn.context`), skip adding READ paths when the action has a `params.get("lines")` parameter.

**Fix (2B):** In the template (`execution_report.md.j2`), add rendering of the line-range content directly in the READ action block (after params rendering, before `render_action_details(log)`), using a proper fenced codeblock. This makes the content visible in the report regardless of session mode.

### Issue 3: Lines/Tail Missing in TUI Right Panel
The `resolve_action_parameters()` function in `textual_plan_reviewer_execution.py` defines what parameters to display per action type via `param_map`. The READ map is `["resource", "description"]` — missing `"lines"`. The EXECUTE map is `["command", "allow_failure", "background", "timeout", "description"]` — missing `"tail"`. These keys exist in `action.params` but are filtered out.

**Fix:** Add `"lines"` to the READ param list and `"tail"` to the EXECUTE param list.

## Implementation Steps

### Step 1: Fix "Metadata Used File Path Alias" in Report
- **File:** [src/teddy_executor/core/services/templates/execution_report.md.j2](/src/teddy_executor/core/services/templates/execution_report.md.j2)
- **Change:** Add `'metadata used file path alias'` to the `param_ns.ignored` list (line ~236). This prevents the generic params loop from rendering the internal plumbing key.

**Current:**
```j2
{% set param_ns = namespace(ignored=['content', 'find', 'replace', 'edits', 'similarity_scores', 'similarity_score', 'similarity threshold', 'similarity_threshold']) %}
```

**Expected:**
```j2
{% set param_ns = namespace(ignored=['content', 'find', 'replace', 'edits', 'similarity_scores', 'similarity_score', 'similarity threshold', 'similarity_threshold', 'metadata used file path alias']) %}
```

### Step 2A: Prevent READ with Lines from Polluting Context
- **File:** [src/teddy_executor/core/services/session_lifecycle_manager.py](/src/teddy_executor/core/services/session_lifecycle_manager.py)
- **Change:** Find where READ paths are added to `T_next/turn.context` during the Turn Transition Algorithm's `finalize_turn` method. Add a guard: if the action type is `READ` and the action has a `lines` parameter (i.e., `params.get("lines")` is truthy), skip adding the path to context.

**Expected Logic:**
```python
# In the loop that processes actions for context addition:
if action.type.upper() == "READ" and action.params.get("lines"):
    continue  # Skip adding READ path to context when Lines is specified
```

Note: If the context addition logic is in `session_orchestrator.py` instead, apply the same guard there. The key is to identify where `T_next/turn.context` gets populated from the current turn's plan actions.

### Step 2B: Render Line-Range Content in Report
- **File:** [src/teddy_executor/core/services/templates/execution_report.md.j2](/src/teddy_executor/core/services/templates/execution_report.md.j2)
- **Change:** Between the params rendering section and the `{{ render_action_details(log) }}` call (before the closing of the action block), add a conditional section for READ actions with Lines that renders the content in a proper fenced codeblock.

**Addition (insert before `{{ render_action_details(log) }}` on the last line of each action block):**
```j2
{% if action_type == 'READ' and log.details and log.details is mapping and log.details.get('content') and params.get('lines') %}
{{ log.details.content | trim | fence }}
{{ log.details.content | trim }}
{{ log.details.content | trim | fence }}
{% endif %}
```

### Step 3: Add Lines/Tail to TUI Param Map
- **File:** [src/teddy_executor/adapters/inbound/textual_plan_reviewer_execution.py](/src/teddy_executor/adapters/inbound/textual_plan_reviewer_execution.py)
- **Change:** In the `resolve_action_parameters` function (line ~55-65), update the `param_map`:
  - READ: Add `"lines"` to the list → `["resource", "lines", "description"]`
  - EXECUTE: Add `"tail"` to the list → `["command", "allow_failure", "background", "timeout", "tail", "description"]`

**Current:**
```python
"READ": ["resource", "description"],
"EXECUTE": ["command", "allow_failure", "background", "timeout", "description"],
```

**Expected:**
```python
"READ": ["resource", "lines", "description"],
"EXECUTE": ["command", "allow_failure", "background", "timeout", "tail", "description"],
```

## Verification
1. Run the test suite: `cd /Users/raphaelatteritano/Desktop/dev/TeDDy && poetry run pytest --timeout 120 -x -q`
2. Manual check: Generate a plan with a READ action that has `Lines: 10-20`, execute it, and verify:
   - The report does NOT contain `- **Metadata Used File Path Alias:** True`
   - The report DOES contain the line-range content in a fenced codeblock within the READ action block
   - The next turn's `input.md` does NOT contain the full file content (only the paths from `turn.context`)
3. Manual check: Select a READ action with Lines in the TUI right panel — verify `Lines: 10-20` is displayed
4. Manual check: Select an EXECUTE action with Tail in the TUI right panel — verify `Tail: 5` is displayed
5. Verify no regressions in existing report formatting and TUI functionality
