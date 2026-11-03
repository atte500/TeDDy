# Slice: Report Formatting Normalization And MESSAGE Relocation
- **Status:** In Progress
- **Milestone:** N/A (ad-hoc)
- **Depends On:** N/A
- **Specs:** N/A (no permanent system invariant changed)
- **Prototype:** N/A (de-risked via throwaway spikes in `spikes/report-formatting-review/`, since removed)
- **Component Docs:** [MarkdownReportFormatter](/docs/architecture/core/services/markdown_report_formatter.md)
- **Scope Slug:** `report-formatting`

## Goal
Normalize the execution report so every file path renders as a single backticked relative path, EXECUTE and RESEARCH subjects render plain, the redundant File Path bullet is removed, duplicate resource headings merge into one, unrecognized details render as fenced JSON, and a MESSAGE action renders as a top-level `## User Reply` instead of a broken `### `MESSAGE`: [](/)` entry inside `## Action Log`. This makes reports scannable in a terminal and reflects that a message turn is a communication, not an action.

## Context
- `MarkdownReportFormatter` renders through `execution_report.md.j2` via a cached Jinja2 `Environment`; `format` post-processes whitespace outside fenced blocks only.
- The current template renders `### `CREATE`: [basename](/abs/path)` links for CREATE/EDIT/READ, wraps the EXECUTE description in double quotes, and falls back to `Execute Command`/`Research` placeholders when no subject exists.
- The template has two independent `{% if %}` guards emitting `## Resource Contents` (one for `failed_resources`, one for `report_ns.resource_logs`), so both render when both are populated.
- The unrecognized-details branch emits the raw object as `- **Details:** `{{ log.details }}``, which renders a Python dict repr.
- Descriptions are stored as `params["Description"]` and render as a `- **Description:**` bullet for CREATE/EDIT/READ; the generic params loop ignores them only for EXECUTE/RESEARCH, where they are the header subject.
- MESSAGE is a message-only turn by MRP mutual exclusivity; its `ActionLog.details` holds the user's reply. Multiple production paths read the MESSAGE `ActionLog` from `report.action_logs` (pipeline stop check, lifecycle synthesis, session orchestrator fallback), so the data must stay there — only the template presentation changes.
- `ReportParser` (test-only observer) splits action chunks by `### `ACTION`` with `(?::\s*(.*))?` and parses resource blocks by `### [`. It strips Markdown links from the subject but not backticks, so the new headings require parser updates; it also parses MESSAGE as an action chunk.

## Scenarios

> As a developer reading an executed report, I want each action's operand shown as a backticked path (or plain description) so I can scan the log without full absolute URLs.

```gherkin
Given an executed CREATE action for src/new_module.py
When the report is rendered
Then the header reads ### `CREATE`: `src/new_module.py`
And no separate - **File Path:** bullet is rendered
And a - **Description:** bullet still renders when the plan supplied one
```

```gherkin
Given an executed EXECUTE action with description "Say hi"
When the report is rendered
Then the header reads ### `EXECUTE`: Say hi
```

```gherkin
Given a report with populated failed_resources and a failing content-bearing READ log
When the report is rendered in non-session mode
Then exactly one ## Resource Contents section renders
```

```gherkin
Given a CREATE action whose details mapping has no recognized keys
When the report is rendered
Then the details render inside a fenced json block
```

```gherkin
Given a report whose only action log is a MESSAGE with reply content
When the report is rendered
Then a top-level ## User Reply section renders with the fenced reply
And no ## Action Log section renders
And no status line renders for the message
```

## Edge Cases
- **URL resource**: If the path starts with `http:` or `https:`, then render it backticked like any other path, because the report is a terminal Markdown artifact and consistency outweighs clickability.
- **Empty subject**: If an EXECUTE or RESEARCH action has no description, then render a bare `### `EXECUTE`` header, because placeholder text such as `Execute Command` or `Research` invents information.
- **Empty file path**: If a CREATE/EDIT/READ log has no path parameter, then render a bare `### `CREATE`` header, not an empty `[](/)` link.
- **Both resource sources populated**: If both `failed_resources` and `resource_logs` are populated, then render a single `## Resource Contents` heading followed by both blocks.
- **Session mode**: If `is_session` is true, then render no `## Resource Contents` section.
- **Non-mapping details**: If `details` is not a mapping, then render the existing `- **Details:**` fallback unchanged.
- **Mapping content for MESSAGE**: If a MESSAGE `details` is a mapping with `content`, then render `content` fenced under `## User Reply`.
- **String details for MESSAGE**: If a MESSAGE `details` is a plain string, then render it fenced under `## User Reply`.
- **Empty MESSAGE details**: If there is no message content, then render no `## User Reply` section, because an empty section adds noise.
- **Mixed logs**: If a report has both MESSAGE and non-MESSAGE actions, then render `## Action Log` for the actions and `## User Reply` separately.
- **Session mode and MESSAGE**: If `is_session` is true, then render MESSAGE the same way; it is not gated by session mode.

## Key Unknowns
No unresolved unknowns. Every rendering decision — backticked paths, plain subjects, merged resource guards, fenced JSON fallback, and top-level `## User Reply` — was reproduced and confirmed against rendered output via throwaway spikes in `spikes/report-formatting-review/` before this slice was authored. Production read paths for the MESSAGE `ActionLog` were confirmed by static trace.

## Impact
1. `[MIGRATE]` `execution_report.md.j2` — backticked path headers, plain EXECUTE/RESEARCH subjects (drop quotes and placeholders), removed File Path bullet, backticked Resource Contents headings, merged resource guards, Title Case `Expected Outcome`, fenced JSON for unrecognized details, and MESSAGE partitioned to a top-level `## User Reply` with `## Action Log` skipped when empty.
2. `[MIGRATE]` `ReportParser` — parse both link-form and backtick-form action subjects and Resource Contents headings, and parse MESSAGE content under `## User Reply`, keeping link-form parsing backward compatible.
3. `[MIGRATE]` Report test suites — update assertions that pin link-form headers, resource headings, `Expected outcome` casing, and MESSAGE-inside-Action-Log placement.
4. `[CONTRACT]` Placeholder fallbacks (`Execute Command`, `Research`), the `- **File Path:**` bullet, and the broken `### `MESSAGE`: [](/)` header with its `- **Status:**` line are removed once tests no longer expect them.

## Deliverables
- [x] **Harness** - Extend `ReportParser` to parse both link-form and backtick-form action subjects and Resource Contents headings, and to read MESSAGE content rendered under `## User Reply`.
- [x] **Core** - Normalize non-MESSAGE action-log rendering in `execution_report.md.j2`: backticked relative-path headers for CREATE/EDIT/READ, plain EXECUTE/RESEARCH subjects (drop the quotes and the `Execute Command`/`Research` placeholders), remove the redundant `- **File Path:**` bullet, backticked `## Resource Contents` headings, merge the two resource guards into one `## Resource Contents` section, Title Case `- **Expected Outcome:**`, and render unrecognized mapping details as a fenced `json` block. Migrate the affected non-MESSAGE report test assertions in the same commit so `make test` stays green (`test_markdown_report_formatter_enhancements.py`, `test_report_modified_actions.py`, and any other raw-string report assertion that pins the old form).
- [x] **Migration** - Relocate MESSAGE rendering to a top-level `## User Reply` section and skip `## Action Log` when the report contains only MESSAGE actions (keep the `*(No actions were executed.)*` note for a truly empty log). Migrate the affected MESSAGE test assertions and snapshots in the same commit (`test_report_message_fencing.py`, the session-lifecycle report assertions, and the acceptance pipeline message flow) so `make test` stays green.

## Implementation Notes
- Change the parser first (accept both formats) so the suite stays green while the template flips.
- Keep the `ReportParser` link-form parsing so older reports remain parseable in tests.
- Partition `report.action_logs` into messages versus actions inside the template; do not change how the report model stores the log.
- Harness as-built: `ReportParser` now exposes a `user_reply` attribute populated by `_parse_user_reply`, which reads the fenced block under a top-level `## User Reply` section. `_parse_resource_contents` splits on both link-form (`### [`) and backtick-form (`### `) headings and extracts the backticked path as a fallback. `_apply_subject_to_params` strips surrounding backticks from CREATE/EDIT/READ subjects. Link-form parsing is retained unchanged for older reports. New unit tests in `tests/suites/unit/test_report_parser.py` cover the backtick-form subject, backtick-form resource heading, and User Reply cases.
- Re-partition (2026-11-03): the template-flip audit showed the raw-string report assertions (`test_markdown_report_formatter_enhancements.py`, `test_report_modified_actions.py`, `test_report_message_fencing.py`, the session-lifecycle report assertions, and the acceptance pipeline message flow) pin the current rendering and are not parser-mediated, so a template-only Core commit would turn the suite red. Core now bundles the non-MESSAGE template normalization with the non-MESSAGE test assertions it breaks; Migration bundles the MESSAGE `## User Reply` relocation with the MESSAGE test assertions it breaks. Each deliverable is atomic and leaves the suite green at its commit.
- Core as-built (`execution_report.md.j2`): CREATE/EDIT/READ headers render a single backticked path via the new branch (`{% set target = '`' ~ full_path ~ '`' %}`); EXECUTE/RESEARCH render the raw description with no quotes and no `Execute Command`/`Research` placeholders, falling back to a bare `### `EXECUTE`` header when no subject exists. A `target == ''` branch renders the bare header without a stray colon. The redundant `- **File Path:**` bullet was deleted (the header carries the path). The two independent `## Resource Contents` guards merged into one `{% if not is_session and (report.failed_resources or report_ns.resource_logs) %}` block emitting a single heading followed by both sources; `render_resource` now emits a backticked `### `path`` heading for all paths including URLs. The `- **Expected Outcome:**` label is Title Case. The unrecognized-mapping details branch renders through `tojson(indent=2) | embed_fence('json')`; the non-mapping string `- **Details:**` fallback is unchanged. The MESSAGE branch is deliberately left on the legacy link-form header so `test_report_message_fencing.py` and the session-lifecycle MESSAGE assertions stay green until Migration. New unit module `tests/suites/unit/core/services/test_report_formatting_normalization.py` pins the nine non-MESSAGE behaviors; the four confirmed breakers were migrated to the backticked form in the same change set.
- Lint unblock (2026-11-03): staging the Core change set surfaced two pre-existing TID251 bare-`MagicMock` violations in `test_textual_plan_reviewer_helpers.py` and `test_markdown_report_formatter_enhancements.py`. Both were repaired in place per the quality-gate bypass policy: the fake `app` object became a `types.SimpleNamespace`, and the template-render stubs became plain capture closures instead of `MagicMock`, so no per-file ignore was added and the obsoleted bare mocks are gone.
- Migration as-built (`execution_report.md.j2`): `report.action_logs` is partitioned once into `split_ns.messages` and `split_ns.actions`, so the Action Log loop iterates only non-message logs. `## Action Log` renders only when `split_ns.actions` is non-empty or the report has no logs at all (preserving `*(No actions were executed.)*` for a truly empty report). The first MESSAGE log carrying `details` renders as a top-level `## User Reply` section fenced through `embed_fence('')` — reading `details.content` for mapping details and the raw string when `details` is a plain string; `params["content"]` (the agent's text) never renders. MESSAGE rendering is not gated by session mode. Once MESSAGE left the action loop, the legacy link-form MESSAGE header and the dead MESSAGE branches in `render_action_blocks` and `render_action_summary` were removed. The three confirmed MESSAGE render breakers (`test_report_message_fencing.py`, `test_session_lifecycle_reply_finalization.py::test_finalized_report_renders_user_reply_not_agent_message`, and the two assertion sites in `test_pipeline_message_and_resume_flow.py`) were migrated to the `## User Reply` form in the same commit; the three session-lifecycle `FORMATTED_REPORT` constants stayed untouched as inert mock return values. New unit module `tests/suites/unit/core/services/test_report_message_relocation.py` pins the five relocation behaviors.

## Verification
1. **Action-plan report rendering:**
   Run `teddy execute` against a plan containing CREATE, EDIT, READ, EXECUTE, and RESEARCH actions.
   Verify the headers read `` ### `CREATE`: `<path>` ``, EXECUTE and RESEARCH subjects are plain, no `- **File Path:**` bullet appears, and any `- **Description:**` bullet still renders.
2. **Resource Contents merge:**
   Execute a plan whose report has a failing READ and a pre-fetched failed resource.
   Verify exactly one `## Resource Contents` section renders.
3. **Unrecognized details:**
   Render a CREATE action whose details mapping has unrecognized keys.
   Confirm the details render inside a fenced `json` block.
4. **Message turn:**
   Run `teddy start`, have the agent respond with a `## Message` plan, and reply.
   Confirm the report shows `## User Reply` with the fenced reply and no `## Action Log`.
5. **Mixed turn:**
   Confirm a report containing both actions and a message shows `## Action Log` and `## User Reply` separately.
