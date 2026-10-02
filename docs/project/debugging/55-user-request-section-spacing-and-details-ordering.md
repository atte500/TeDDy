# Bug: `## User Request` Section Spacing & Action-Log Field Ordering

- **Status:** Resolved
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
- 5a: `SessionLifecycleManager._append_user_request` concatenates `content += f"\n## User Request\n..."` (single leading `\n`). Because `finalize_turn` persists `formatter.format(report)`, which ends with `.strip()` (no trailing newline), the heading is preceded by exactly one `\n` — no blank line. VERIFIED by MRE (append path: heading preceded by `'ESS\n'`). The Jinja template's `## User Request` block ALREADY renders a blank line before the heading (MRE control: chars before heading `'k`\n\n'`), so 5a is confined to the append path alone.
- 5b: the `- **Details:**` line is emitted by the shared `render_action_details` macro, invoked at the very END of each action block (`execution_report.md.j2:281`), after the EXECUTE-specific `- **Status:**` / `- **Expected outcome:**` / `- **Command:**` fields. VERIFIED by MRE (rendered EXECUTE: `index(status)=216 index(details)=297 index(command)=273`). The macro is shared by ALL action types and ALSO emits rich diagnostic blocks (`#### stdout`, `#### stderr`, `#### diff`, `- **Error:**`, `- **Return Code:**`, `- **Failed Command:**`) when `details` is a mapping — so a wholesale relocation of the macro relocates those blocks as well.

### Discrepancies
- The `render_action_details` macro is shared by all action types; the requested reordering was stated for EXECUTE specifically. Whether `- **Details:**` should follow `- **Status:**` for ALL action types or only EXECUTE is UNRESOLVED. (resolved: the user approved the uniform split-macro contract at Alignment — scalar summary metadata hoists under `- **Status:**` for ALL action types; rich multi-line blocks stay at block end. User reply: "ok thats fine".)
- The macro emits BOTH the single-line `- **Details:**` (plain-string `details`) AND rich multi-block diagnostics (`#### stdout` / `#### stderr` / `#### diff` / `- **Error:**` / `- **Return Code:**` for mapping `details`). Whether the fix should relocate the whole macro (moving stdout/stderr/diff ABOVE Expected outcome/Command for a failed EXECUTE) or hoist only the single-line summary is UNRESOLVED and must be settled with the user in Alignment. (resolved: the shadow probe — Investigation History #5 — proves hoisting ONLY the scalar summary preserves stdout/stderr/diff at block end; the naive whole-macro relocation is rejected because it would render command output/diffs ABOVE the command itself.)

### Investigation History
1. Hypothesis: the append path lacks a blank-line separator. Observation: `_append_user_request` uses a single leading `\n`. Conclusion: 5a confirmed.
2. Hypothesis: the template emits Details last. Observation: `render_action_details(log)` is invoked at the end of the action block. Conclusion: 5b confirmed.
3. Hypothesis: the MRE reproduces both defects against real `src/` components. Observation: `spikes/debug/55-user-request-spacing-and-details-ordering-mre.py` exits `1`; 5b FAIL (`index(details)=297 > index(command)=273`), 5a-append FAIL (heading preceded by `'ESS\n'`), 5a-template OK (heading preceded by `'k`\n\n'`). Conclusion: 5a is confined to the `_append_user_request` path — the template already emits the blank line; 5b verified against rendered output.
4. Hypothesis: splitting `render_action_details` into a scalar `render_action_summary` (invoked right after `- **Status:**`) plus `render_action_blocks` (invoked at block end), combined with `.rstrip("\n")` + `"\n\n"` in `_append_user_request`, fixes both defects. Observation: shadow MRE (`BUG55_SHADOW=1`) exits `0`, all three checks OK (`OVERALL: PASS`): 5b `index(status)=216 index(details)=238 index(command)=340` (`status < details < command`); 5a-append heading preceded by `'SS\n\n'` (blank line restored); 5a-template unchanged OK. Real MRE still exits `1`. Conclusion: BOTH fixes empirically proven against shadow copies with zero `src/` changes.
5. Hypothesis: the split macro preserves the rich diagnostic blocks (`#### stdout`/`#### stderr`/`#### diff`/`- **Return Code:**`) at block end. Observation: shadow probe renders a mapping-details FAILED EXECUTE with `- **Return Code:**` hoisted to just after `- **Status:**` while `#### stdout`/`#### stderr` stay at block end; CREATE-with-diff keeps `#### diff` at block end. Conclusion: the fix hoists ONLY scalar summary metadata and leaves multi-line diagnostics in place — no output-before-command regression.
6. Hypothesis: the user approves the uniform split-macro contract and the stdout/stderr fencing. Observation: Alignment — user confirmed 5a ("5a ok"), reviewed the full BEFORE/AFTER rendering map across 13 action types/conditions and approved 5b ("ok thats fine"), confirmed `stdout`/`stderr` remain code-fenced, and granted the final go-ahead ("ok proceed"). Conclusion: both fixes design-approved; no design change required.
7. Hypothesis: the change set is bounded to the report surface with no Port/Signature/DTO impact. Observation: Systemic Audit (Turn 16) — `render_action_details` is defined+invoked ONLY in `execution_report.md.j2` (5b blast radius: 1 file); the `## User Request` format is duplicated across the template + `_append_user_request` + `session_service`'s position-independent `^## User Request` detection regex (unaffected by the blank-line change); `_append_user_request` has 1 definition + 2 callers; `- **Details:**` test assertions are MESSAGE-scoped (`test_report_message_fencing.py`) or parser-based (`test_formatter_action_logs.py`, `test_report_parsing_helpers.py`) and not position-sensitive. Conclusion: no Vertical Slice partitioning required — a direct (trivial) fix touching 2 production files + a bounded set of test assertions.

## Solution

### Root Cause
Both findings are layout defects in the Markdown report surface.

- **5a (missing blank line before `## User Request`, append path):** `SessionLifecycleManager._append_user_request` concatenated the section with a single leading `\n` (`content += f"\n## User Request\n..."`). Because `finalize_turn` persists `formatter.format(report)`, which `.strip()`s the report, the on-disk `report.md` has NO trailing newline, so the single `\n` produced a line break but not a blank-line separator. The Jinja template path was already correct (its block emits the blank line), so 5a was confined to the append path alone.
- **5b (`- **Details:**` after `- **Command:**`):** `execution_report.md.j2` invoked the single shared `render_action_details(log)` macro at the very END of every action block. That macro emits BOTH (a) scalar, status-adjacent metadata (`- **Details:**`, `- **Error:**`, `- **Return Code:**`, `- **Failed Command:**`, `- **Similarity Score(s):**`) and (b) multi-line diagnostic blocks (`#### stdout`, `#### stderr`, `#### diff`) plus the MESSAGE reply. Running last, the scalar `- **Details:**` landed after the EXECUTE-specific `- **Command:**`.

### Fix (Verified via Shadow-File MRE)
- **5a:** `.rstrip("\n")` the report body then prepend `"\n\n"` — guarantees exactly one blank line before the heading regardless of the persisted body's trailing-newline state (idempotent even when the body already ends in newlines).
- **5b:** Split the shared macro into `render_action_summary(log)` (scalar metadata, invoked directly after `- **Status:**`) and `render_action_blocks(log)` (multi-line diagnostics + MESSAGE reply, invoked at block end, unchanged position). This hoists ONLY the scalar summary; `#### stdout`/`#### stderr`/`#### diff` stay at block end, avoiding the regression of rendering command output/diffs ABOVE the command.

### Evidence
- Shadow MRE (`BUG55_SHADOW=1 .../55-user-request-spacing-and-details-ordering-mre.py`) exits `0`, all checks OK: `index(status)=216 < index(details)=238 < index(command)=340`; 5a-append heading preceded by a blank line.
- Real MRE still exits `1` (baseline unchanged) -> zero `src/` impact during verification.
- Shadow probe confirms mapping-details shapes: `- **Return Code:**` hoisted after Status; `#### stdout`/`#### stderr`/`#### diff` retained at block end.

### Preventative Measures (systemic)
- The `## User Request` format is duplicated across two production sites (template + `_append_user_request`). Extract a single shared format helper/constant consumed by both so they cannot drift apart (already logged in PROJECT.md Technical Debt).
- Keep "status-adjacent scalar summary" and "block-level diagnostics" as distinct template concerns so future field additions cannot silently inherit the wrong placement.
