# Slice: Embed-Seam Consolidation
- **Status:** In Progress
- **Milestone:** Ad-hoc (not tracked in the Roadmap per PROJECT.md)
- **Depends On:** [00-38-session-hang-fence-sanitization.md](./00-38-session-hang-fence-sanitization.md) (Completed; provides the shared `embed_in_fence` seam)
- **Specs:** N/A (consolidation; no permanent system invariant changes)
- **Prototype:** N/A (the seam is proven by slice 00-38 and the case-file MREs)
- **Component Docs:** [MarkdownReportFormatter](/docs/architecture/core/services/markdown_report_formatter.md), [ContextService](/docs/architecture/core/services/context_service.md)
- **Scope Slug:** `embed-seam`

## Business Goal
Route every remaining `get_fence_for_content` call site through the shared `embed_in_fence` seam so a degenerate unclosed fence can no longer amplify a generated Markdown block. This bounds the "unbounded/amplified embed" category at one seam.

## Scenarios
> As a user, I want every generated fenced block to stay bounded so that a single degenerate LLM output cannot inflate a report, diagnostic, or validation message.

```gherkin
Given content containing an unclosed giant backtick run
When a generated fenced block is assembled at any migrated site
Then the block is bounded and no fence amplification occurs
```

## Edge Cases
- **Preserve balanced block**: If content is well-formed Markdown, then the assembled block is byte-for-byte identical to the pre-migration output, because the migration is behaviour-preserving.
- **Preserve empty language**: If a site uses a bare fence with no language suffix, then `embed_in_fence(content, "")` yields the same bare block.
- **Bounded validation diagnostic**: If a FIND block or diff contains an unclosed fence, then the diagnostic message is bounded.
- **Bounded report block**: If a message action contains an unclosed fence, then the rendered report block is bounded.
- **No fences**: If content has no fence lines, then the block is unchanged.

## Key Unknowns

**Taxonomy:** see template.

- [x] [Technical] Per-site output equivalence: RESOLVED — every remaining site composes its block as `fence + lang + "\n" + content + "\n" + fence` (or the bare-fence variant), which equals `embed_in_fence(content, lang)` when the content has no unclosed fence. The migration is byte-preserving for well-formed content. Design Sensitivity: if a site composed its block differently, that site would need a bespoke wrapper instead of `embed_in_fence`.
- [x] [Technical] Jinja filter arity: RESOLVED — the `fence` filter returns only a bare fence string and is called twice per block; it must become a two-argument `embed_fence` filter called once per block, with the template updated at every `| fence` site. Design Sensitivity: if the filter could return a full block, no template change would be needed.

## Impact
1. `[MIGRATE]` `SessionLifecycleManager._append_user_request` — route the `## User Request` embed through `embed_in_fence`.
2. `[MIGRATE]` `validation_rules/edit.py` — route the FIND-block and diff embeds through `embed_in_fence`.
3. `[MIGRATE]` `parser_reporting.py` — route the expected-structure, AST-view, and structural-mismatch embeds through `embed_in_fence`.
4. `[MIGRATE]` `MarkdownReportFormatter` + `execution_report.md.j2` — replace the `fence` Jinja filter with an `embed_in_fence`-backed filter.
5. `[CONTRACT]` none — no port signature changes.

## Deliverables

- [ ] **Migration** — Route `SessionLifecycleManager._append_user_request` through `embed_in_fence`. Add a unit test to `tests/suites/unit/core/services/test_session_lifecycle_user_request_spacing.py` proving the normal output is byte-identical and a degenerate message is bounded.
- [ ] **Migration** — Route `validation_rules/edit.py` (the FIND-block and diff embeds) through `embed_in_fence`. Add unit tests to `tests/suites/unit/core/services/test_validator_edit.py` proving normal diagnostics are unchanged and a degenerate FIND block is bounded.
- [ ] **Migration** — Route `parser_reporting.py` (the expected-structure, AST-view, and structural-mismatch embeds) through `embed_in_fence`. Add unit tests to `tests/suites/unit/core/services/test_parser_reporting.py` proving normal diagnostics are unchanged and a degenerate AST is bounded.
- [ ] **Migration** — Replace the `fence` Jinja filter in `MarkdownReportFormatter` with an `embed_in_fence`-backed `embed_fence` filter and update `execution_report.md.j2` to call it once per block. Add a test to `tests/suites/unit/core/services/test_report_message_fencing.py` proving a degenerate message action yields a bounded report block.
- [ ] **Cleanup** — Update the component docs (`markdown_report_formatter.md`, `context_service.md`) to record the single seam. Run `git grep -n "get_fence_for_content" -- src` and confirm only `core/utils/markdown.py` matches.

## Implementation Notes
- **No Wiring deliverable.** The consolidation reuses the existing `embed_in_fence` seam and introduces no new boundary, so no hardcoded-skeleton tracer bullet applies. This mirrors slice 00-38's documented precedent.
- **Byte-preservation contract.** Each migrated site already composes its block as `fence + lang + "\n" + content + "\n" + fence` (or the bare-fence variant), so the migration is byte-preserving for well-formed content. A site whose content ends in a newline must strip that newline before delegating.
- **Jinja filter.** The `fence` filter is replaced by a two-argument `embed_fence` filter; the template calls it once per block instead of twice.
- **Deferred residual.** A BALANCED giant run (a well-formed block whose delimiter is a giant run) evades unclosed-fence detection and is NOT collapsed by this slice. Case file 07 Preventative Measure 1 defers it ("address it only if such a case ever appears"), and the user rejected a threshold guard in favor of the semantic detector. The migration is therefore byte-preserving for all well-formed content, including a balanced giant run.

## Verification
- [ ] **CLI:** Run `make test` and verify the full suite passes (green-to-green).
- [ ] **Unit:** Run `uv run pytest tests/suites/unit/core/utils/test_markdown_utils.py -q` and verify the seam tests pass.
- [ ] **CLI:** Run `git grep -n "get_fence_for_content" -- src` and verify only `core/utils/markdown.py` matches.
