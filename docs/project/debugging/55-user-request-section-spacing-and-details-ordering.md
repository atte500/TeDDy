# Bug: `## User Request` Section Spacing & Action-Log Field Ordering

- **Status:** Unresolved
- **Milestone:** N/A (ad-hoc slice)
- **Vertical Slice:** [00-21-session-interrupt-resume-message.md](/docs/project/slices/00-21-session-interrupt-resume-message.md)
- **Specs:** [report-format.md](/docs/project/specs/report-format.md)

## Symptoms

Two report-formatting findings surfaced during slice verification.

### 5a — Missing blank line before `## User Request`
When `teddy resume -m "..."` appends a `## User Request` section to an existing `report.md` (via `SessionLifecycleManager._append_user_request`), the section is NOT preceded by a blank line. Expected: a blank line separating the section from the preceding report body — and the same in the Jinja template render path.

### 5b — `- **Details:**` renders AFTER `- **Command:**` in the template
For an `EXECUTE` action, `execution_report.md.j2` renders `- **Details:**` AFTER `- **Command:**` (observed on a SKIPPED EXECUTE action):
```
### `EXECUTE`: "List the vertical slices ..."
- **Status:** SKIPPED
- **Expected outcome:** ...
- **Command:**
```shell
...
```

- **Details:** `User deselected this action in the plan reviewer.`
```
Expected (user): `- **Details:**` should render directly after `- **Status:**`, before `- **Expected outcome:**` / `- **Command:**`:
```
### `EXECUTE`: "List the vertical slices ..."
- **Status:** SKIPPED
- **Details:** `User deselected this action in the plan reviewer.`
- **Expected outcome:** ...
- **Command:**
```shell
...
```
```

## Context & Scope

### Regressing Delta
- 5a — `SessionLifecycleManager._append_user_request` builds `content += f"\n## User Request\n{fence}text\n{message}\n{fence}\n"` (single leading `\n`); the template block was relocated to the END by commit `bf927e63`.
- 5b — `execution_report.md.j2` invokes the generic `render_action_details(log)` macro at the END of each action block, so `- **Details:**` lands after the EXECUTE `- **Command:**` section.

### Environmental Triggers
Any `resume -m` on a completed turn (5a); any report containing an EXECUTE action carrying `details` (5b).

### Ruled Out
- `session_service`'s `^## User Request` prune-preservation detection (position-independent line scan) — unaffected by a blank-line/ordering change.
- The smart-fencing length computation (`get_fence_for_content`) — correct.

## Diagnostic Analysis

### Causal Model
- 5a: `_append_user_request` concatenates the section with a single `\n` separator; if the existing report body does not already end with a blank line, no blank line separates the two. The relocated template block relies on `trim_blocks` behaviour for its leading blank line — the user asked to make this explicit/consistent.
- 5b: the `- **Details:**` line is emitted by the shared `render_action_details` macro, invoked at the very end of the action block — after the EXECUTE-specific `- **Status:**` / `- **Expected outcome:**` / `- **Command:**` fields.

### Discrepancies
- The `render_action_details` macro is shared by all action types; the requested reordering was stated for EXECUTE specifically. Whether `- **Details:**` should follow `- **Status:**` for ALL action types or only EXECUTE is UNRESOLVED.

### Investigation History
1. Hypothesis: the append path lacks a blank-line separator. Observation: `_append_user_request` uses a single leading `\n`. Conclusion: 5a confirmed.
2. Hypothesis: the template emits Details last. Observation: `render_action_details(log)` is invoked at the end of the action block. Conclusion: 5b confirmed.

## Solution
_(To be completed by the Debugger.)_

Fix directions: add an explicit blank-line separator before `## User Request` in both `_append_user_request` and the template; reorder the template so `- **Details:**` renders after `- **Status:**` (scope per the discrepancy above). Preventative: a single shared `## User Request` format helper/constant consumed by both sites (already logged in PROJECT.md Technical Debt).
