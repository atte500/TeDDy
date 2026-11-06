# Slice: Report Action Headline And RESEARCH Rendering Polish
- **Status:** Completed
- **Milestone:** N/A (ad-hoc)
- **Depends On:** N/A
- **Specs:** N/A (the report-format spec delegates the concrete render format to the Jinja template; no permanent invariant changes)
- **Prototype:** N/A (de-risked with throwaway render probes during the Pathfinder discovery turns)
- **Component Docs:** [MarkdownReportFormatter](/docs/architecture/core/services/markdown_report_formatter.md)
- **Scope Slug:** `report-headlines`

## Goal
Make execution reports scannable by leading each file action with its filename while keeping the full path in a body bullet, stop restating EXECUTE commands that match the plan, and polish the RESEARCH block with a SERP label, explicit empty-result reporting, and a purpose-naming hint.

## Context
- `MarkdownReportFormatter` renders through `execution_report.md.j2` with a cached Jinja2 environment; the formatter only post-processes whitespace outside fenced blocks.
- Slice `00-14` replaced link-form headers with backticked full-path headers and deleted the `- **File Path:**` bullet because "the header carries the path". This slice reverses that trade-off: the headline shortens to the basename, the full path returns as a bullet, and the headline subject becomes plain so every action type shares one shape (backticked action type, plain subject).
- The headline path resolves through `params.get('File Path') or params.get('file_path') or params.get('Resource') or params.get('resource') or params.get('path')`. The `basename` filter is already registered on the Jinja environment.
- `ReportParser` already absorbs the proposed format. A render-and-parse probe produced `### `CREATE`: new_file.py` plus `- **File Path:** `src/new_file.py`` and parsed back `{"File Path": "src/new_file.py"}`; a READ produced `{"File Path": "docs/config.yaml", "Resource": "config.yaml"}`, so the headline subject still seeds `Resource` with the basename while the bullet carries the full path.
- EXECUTE renders `- **Command:**` inline for single-line commands and fenced for multiline commands. Both workflows retain the plan: a session report is paired with `plan.md` in the next turn's context, and a clipboard report is pasted into a chat that already carries the plan. A command diverges from the plan only when it was edited in the reviewer (`modified_fields` contains `command`).
- RESEARCH descriptions are normally present, and the header already renders them plainly since slice `00-14`; a description-less action keeps today's bare `### `RESEARCH`` header and must not invent a subject from its queries. The query block today renders `#### Query: "<query>"` and closes with the unconditional shouty line `_**Hint:** NOW you MUST use READ on the most promising results_`.
- The per-result `description` is the SERP snippet the search engine placed in the result listing, not the page's `<meta name="description">`: `WebSearcherAdapter` maps ddgs `body` to `description`, ddgs defaults to `backend="auto"`, and probes showed the same URL yields different snippets across backends and never matched the page's meta tag verbatim. `title` is likewise the SERP result title.
- The project does not enrich results with page metadata today: `WebScraperAdapter.get_content` returns extracted Markdown only and discards `trafilatura` metadata. A probe measured about 1.48 s to fetch five pages sequentially, with one page returning a 403, so enrichment costs latency and is out of scope (confirmed no custom enrichment by the user).
- When one query fails inside a multi-query action the adapter returns `results: []` rather than an error entry, so empty and failed queries look identical in the report. A partial-failure probe rendered empty `#### Query:` sections without crashing; a missing `results` key iterates as an empty sequence under Jinja.

## Scenarios

> As a developer scanning a long execution report, I want each file action to lead with its filename and keep the full path in a bullet, so the action is fast to find and the path stays available.

```gherkin
Given an executed CREATE action for src/new_module.py
When the report is rendered
Then the header reads ### `CREATE`: new_module.py
And the body renders - **File Path:** `src/new_module.py`
```

```gherkin
Given an executed READ action for a root-level README.md
When the report is rendered
Then the header reads ### `READ`: README.md
And no - **File Path:** bullet renders
```

```gherkin
Given a CREATE action the user edited in the plan reviewer
When the report is rendered
Then the header reads ### `CREATE` (user modified: content): new_file.py
```

> As a developer reviewing an executed plan, I want the report to show a command only when it diverges from the plan or failed, so the log stays concise without losing the audit trail.

```gherkin
Given a successful EXECUTE action whose command was not modified
When the report is rendered
Then no - **Command:** block renders
```

```gherkin
Given an EXECUTE action whose command the user edited in the reviewer
When the report is rendered
Then - **Command:** renders the executed command
```

```gherkin
Given a failed EXECUTE action
When the report is rendered
Then - **Command:** renders the executed command
```

> As a developer reading a research turn, I want to see the query and its SERP results clearly, so I can scan findings without deciphering a quoted label or guessing whether a query returned nothing.

```gherkin
Given a RESEARCH action with description Research provider routing
When two queries return results
Then the header reads ### `RESEARCH`: Research provider routing
And each query block renders as #### SERP for "<query>"
And the block ends with *Hint: Use READ on a result URL to fetch the page contents.*
```

```gherkin
Given a RESEARCH query that returned no results
When the report is rendered
Then the query section renders *(No results returned.)*
```

```gherkin
Given a RESEARCH action where every query returned no results
When the report is rendered
Then no *Hint:* line renders
```

```gherkin
Given a RESEARCH action with no description
When the report is rendered
Then the header renders a bare ### `RESEARCH` with no invented subject
```

## Edge Cases
- **URL resource**: If the resolved path starts with `http:` or `https:`, then render the full URL as the headline and skip the File Path bullet, because a URL basename drops the meaningful host and path structure.
- **Path equal to basename**: If the resolved path contains no directory component, then skip the File Path bullet, because it would repeat the headline.
- **Missing path parameter**: If a file action has no path parameter, then render a bare `### `CREATE`` header and no File Path bullet.
- **Modified tag**: If `modified_fields` is non-empty, then keep the existing tag between the action type and the filename.
- **Multiline failed command**: If the command contains a newline, then keep the fenced block; the gate depends on modification and status, not command shape.
- **Missing command parameter**: If the action carries no command parameter, then render no command block regardless of status.
- **Missing results key**: If a query entry omits `results`, then render the no-results note rather than an empty section.
- **Empty results list**: If a query entry carries `results: []`, then render the no-results note, matching a failed query.
- **Empty result fields**: If a result carries an empty title or description, then omit that bullet and keep the link and any remaining bullet.
- **No description**: If a RESEARCH action has no description, then render a bare `### `RESEARCH`` header and never derive a subject from the query list, because descriptions are normally supplied and the header already renders them plainly since slice 00-14.
- **Quoted query**: The query always renders verbatim inside double quotes, so the label reads `#### SERP for "<query>"`.
- **Description label**: The per-result snippet keeps the `- **Description:**` label (confirmed by the user); no page-meta enrichment is added.
- **Session mode**: If `is_session` is true, then render all three changes identically, because none of them is gated by session mode.
- **No query_results**: If `query_results` is absent, then keep the current behavior and render no query section.

## Key Unknowns
No unresolved unknowns. Throwaway probes confirmed the parser round-trip on the proposed headline and bullet format, confirmed partial-failure RESEARCH data renders without raising, established that `description`/`title` come from the SERP rather than page metadata, and measured the cost of meta-description enrichment. The remaining format decisions (plain basename, conditional command block, SERP label, hint wording, `Description` label, no enrichment) are product choices confirmed with the user at the Pathfinder alignment gate.

## Impact
1. `[MIGRATE]` `execution_report.md.j2` — basename headline and restored File Path bullet for CREATE/EDIT/READ, conditional EXECUTE command block, and RESEARCH `#### SERP for "<query>"` heading, no-results note, non-empty bullets, and gated reworded hint.
2. `[MIGRATE]` Report-output assertions — `test_textual_plan_reviewer_helpers.py`, `test_markdown_report_formatter_enhancements.py`, `test_report_formatting_normalization.py`, `test_context_aware_editing.py`, `test_formatter_action_logs.py`, and `test_report_formats_integration.py`, confirmed by a repository-wide grep sweep for report-output action headings and research markers.
3. `[CONTRACT]` The `- **Command:**` block becomes conditional on modification or failure, the File Path bullet becomes the canonical carrier of the full path in the report body, and the RESEARCH query label becomes `SERP for "<query>"`.

## Deliverables
- [x] **Core** - File-action headlines: render the basename of the resolved full path as a plain headline subject, add the backticked `- **File Path:**` bullet only when the path carries a directory component, preserve the modified tag, and keep the full URL for URL resources. Migrate the report assertions that pin the old backticked full-path headline in the same change set so `make test` stays green.
- [x] **Core** - EXECUTE command gating: render the command block only when the command was user-modified or the action did not succeed. Migrate the assertions that expect the block for an unmodified success in the same change set.
- [x] **Core** - RESEARCH rendering: render `#### SERP for "<query>"` with the query verbatim in quotes, render the no-results note, omit empty result bullets, and gate the reworded hint on at least one result. Keep the `- **Description:**` label and add no metadata enrichment. Migrate the research assertions in the same change set and pin the new behaviors with unit coverage.

## Implementation Notes
- Deliver in three atomic commits (file headlines, EXECUTE gating, RESEARCH polish), each leaving `make test` green; the template change and the assertions it breaks land together because the assertions pin raw rendered strings.
- Keep `ReportParser` unchanged: the probe proved it already reads the File Path bullet over the headline subject. For READ, the headline subject still seeds `Resource` with the basename; consumers that need the full resource read `File Path`.
- No specification amendment: the report-format spec delegates the concrete render format to the canonical template, following the same precedent as slice `00-14`.
- The command gate keeps the audit trail intact: a deviation the reviewer introduced stays visible, and a failure keeps the executed command; only an unmodified success omits it, and in both workflows the plan remains available to the next turn.
- The hint reads `*Hint: Use READ on a result URL to fetch the page contents.*` and renders only when at least one query returned a result. It names READ's purpose because the SERP carries snippets only; the agent fetches full page content through READ.
- The `- **Description:**` label stays even though the value is the engine's SERP snippet: the user confirmed the current label, and the domain DTO already documents the field as "The SERP snippet". Page-meta enrichment (fetching `meta description` per result) is out of scope and would be its own slice on `WebSearcherAdapter`.

- **Deliverable 1 (file-action headlines) landed:** `execution_report.md.j2` resolves `full_path` once at the top of the action loop, keeps the full URL as the subject for `http:` and `https:` resources, shortens a nested path through the registered `os.path.basename` filter while emitting the backticked `- **File Path:**` bullet, and leaves a root-level path bare with no bullet. Assertions migrated in six modules, with new root-level and URL coverage added to `test_report_formatting_normalization.py`. `ReportParser` needed no change: the body bullet overrides the basename headline subject, so a READ consumer still reads the full resource from `File Path`.
- **Deliverable 2 (EXECUTE command gating) landed:** `execution_report.md.j2` computes `command_diverged = 'command' in (log.modified_fields or []) or log_status != 'SUCCESS'` and renders the `- **Command:**` block only when a command exists AND that condition holds. Inline versus fenced rendering is unchanged, so a reviewer-edited or failed multiline command keeps its fenced form. `test_formats_multiline_execute_command_correctly` was migrated to carry `modified_fields=["command"]`, `test_report_action_summary_ordering.py` keeps its details-before-command ordering assertion meaningful by marking the command reviewer-modified, and `test_formatter_action_logs.py` pins five branches (unmodified success omits, modified inline, failed inline, failed multiline, missing command). The reviewer echo renders the same gate as the final report, so TUI detail-pane parity holds by construction. The integration gate surfaced one further stale pin: `test_ast_parser_resilience_wiring.py` used the rendered `echo success` text as a proxy for execution, so it now parses the report through `ReportParser` and asserts the EXECUTE action's SUCCESS status and captured stdout instead.
- **Deliverable 3 (RESEARCH rendering) landed:** `execution_report.md.j2` renders `#### SERP for "<query>"` with the query verbatim in quotes, reads each query's results through `qr.get('results') or []` so both `results: []` and a missing `results` key render `*(No results returned.)*`, guards the `- **Title:**` and `- **Description:**` bullets on non-empty values while keeping the numbered link, and renders `*Hint: Use READ on a result URL to fetch the page contents.*` only when a `research_ns` namespace recorded at least one result across all queries. `test_formatter_action_logs.py` migrated both research tests to the SERP label and added four branch tests (empty results, missing key, mixed-query hint gating, empty-field omission); `test_report_formats_integration.py` migrated its hint assertion. No adapter or parser change was needed, and no page-metadata enrichment was added.
- **Verification audit:** confirmed no live stale render marker remains in `src/` or `tests/` (the only `Query:` and old-hint mentions are this slice's historical Context section), the template carries no TODO or placeholder markers, and the four formatter consumers (`SessionLifecycleManager`, the CLI `execute` flow, the `TextualPlanReviewer` echo, and the composition root) render through the one updated template. The full suite is green at 2274 passed, 5 skipped after the pruned duplicate test. The untested fallback link-form branch is recorded as debt in `docs/project/PROJECT.md` under Milestone 6.

## Verification
1. **File-action headlines:**
   Run `teddy execute -y --no-copy --plan-content` with a plan containing a nested CREATE, a nested EDIT, and a root-level READ.
   Verify each header shows the filename, the nested actions render a `- **File Path:**` bullet with the full path, and the root-level READ renders no bullet.
2. **EXECUTE command gating:**
   Run the same plan with an unmodified EXECUTE action and confirm no `- **Command:**` block renders.
   Review a plan in the TUI, edit an EXECUTE command, submit, and confirm the report renders the edited command.
   Run a failing EXECUTE action and confirm the report renders the command block.
3. **RESEARCH rendering:**
   Run a research plan with two queries and confirm the header shows the description, each query heading reads `#### SERP for "<query>"` with the query verbatim in quotes, per-result bullets read `- **Title:**` and `- **Description:**`, and the closing line reads `*Hint: Use READ on a result URL to fetch the page contents.*`.
   Run a query that returns no results and confirm the section renders `*(No results returned.)*` and, when every query is empty, no hint line renders.
4. **TUI parity:**
   Execute an action from the plan reviewer and confirm the detail pane renders the same headline, bullet, and research formatting as the final report.
