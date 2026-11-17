# Slice: Rationale Section Consolidation
- **Status:** Completed
- **Milestone:** N/A (ad-hoc)
- **Depends On:** N/A
- **Specs:** [Plan Format](/docs/project/specs/plan-format.md), [Interactive Session Workflow](/docs/project/specs/interactive-session-workflow.md)
- **Prototype:** N/A
- **Component Docs:** [TextualPlanReviewer](/docs/architecture/adapters/inbound/textual_plan_reviewer.md)
- **Scope Slug:** `rationale-sections`

## Goal
Deliver a four-section rationale contract — `Summary`, `Expectation`, `Progress`, `Notes` — whose wording is locked in the MRP and whose sections render as navigable nodes in the plan reviewer.

## Context
- `MarkdownPlanParser`: carries the rationale as one opaque string. No parser or domain-model change is required.
- `ALLOWED_RATIONALE_SECTIONS` (defined in `textual_plan_reviewer_logic.py`): gates node creation in `handle_mount_logic` (`textual_plan_reviewer_helpers.py`). A title outside the list is appended to the previous node's content.
- `MarkdownPlanBuilder`: emits the old `1. Synthesis` through `4. State Dashboard` default, so the shared harness must move with the protocol.
- `plan-format.md`: pins the rationale shape and still teaches `Expected Outcome` plus the deprecated `PROMPT`/`INVOKE` actions in its comprehensive example.
- `debugger.md`: names a workflow step `Synthesis Presentation`; it must become `Summary Presentation` so one concept keeps one word.
- Exact drift inventory, re-derived across the tree: `plan-format.md` lines 67 and 72–81 (the rationale format) plus 235–244 (the comprehensive example, which also teaches the deprecated `PROMPT`/`INVOKE`); `debugger.md:78` (`Synthesis Presentation`); `README.md:84` (the "synthesis, justification, and expected outcomes" sentence); and `tests/harness/drivers/plan_builder.py` lines 218–227 (the default rationale). Twelve test modules carry the old titles: `test_tui_instruction_bridge.py`, `test_tui_rationale_parsing.py`, `test_tui_rationale_scrolling.py`, `test_resilient_edit_matching_integration.py`, `test_validation_diagnostics_integration.py`, `test_rationale_filtering.py`, `test_section_filtering.py`, `test_markdown_plan_parser_session.py`, `test_normalize_h1.py`, `test_parser_create_overwrite.py`, `test_parser_path_retention.py`, and `test_plan_builder.py`.
- `test_section_filtering.py` asserted the legacy allowlist names on purpose at discovery, so it was not drift then, and `test_rationale_filtering.py` exercised legacy-section rendering. A later direct user order narrowed the allowlist to the four protocol sections and dropped numeric-marker parsing, superseding both (see Implementation Notes).
- `interactive-session-workflow.md` carries no rationale section names and needs no change.
- `plan-format.md`'s `Expected Outcome` mentions at lines 174 and 189 are the `EXECUTE` parameter covered elsewhere in the spec, not rationale vocabulary; leave them untouched.
- The MRP wording is already updated in this slice. The remaining work synchronizes the spec, harness, prompt vocabulary, tests, and the stale README sentence.
- The MRP `## Response Format` was consolidated while this slice was open: `No Preamble` and `Response Termination` merged into `Response Boundaries`; `Rationale Encapsulation` absorbed into a single `Code Block Formatting` whose nesting rule wins over the old "exactly 4" wording; `Progress and Notes` deleted in favor of the `### Structure` template; and the Action Plan/Message exclusivity rule moved beneath that template.
- `plan-format.md`'s *Code Block Nesting* section still speaks only of backticks and pins a fence strictly greater than the longest backtick run, while the MRP now admits tilde fences under the same nesting rule. The two must agree before the spec can be called aligned.

## Scenarios
> As a plan reviewer, I want the rationale tree to expose Summary, Expectation, Progress, and Notes as separate nodes so that I can move through the whole story without scrolling a single blob.

```gherkin
Given a plan whose rationale uses the four protocol sections
When the plan reviewer builds the Rationale tree
Then the tree shows Summary, Expectation, Progress, and Notes as sibling nodes
And each node contains only its own section content
```

## Edge Cases
- **Legacy rationale**: If a resumed session stores `Synthesis`, `Justification`, or `State Dashboard`, those titles no longer create nodes; each legacy section's content is appended to the preceding accepted section, and a leading legacy section is dropped.
- **Unknown heading**: If a rationale contains an unrecognized `###` title after a recognized section, then its content remains appended to the previous node, preserving the current fallback behavior.
- **Missing expectation**: If a plan omits `Expectation`, then the Status binding loses its anchor, so the protocol test must fail the slice.
- **Summary scope**: If `Summary` only recaps the previous turn, then the section violates the protocol requirement to carry the whole session story.

## Key Unknowns
No open unknowns. The protocol wording is locked by the MRP; remaining work is mechanical synchronization.

Resolved during discovery:
- [x] `[Domain]` Section names and semantics: Resolved by the locked MRP wording. Design Sensitivity: fixed names become the TUI allowlist and spec vocabulary.
- [x] `[Technical]` Parser impact: Resolved by static reading. The rationale is opaque text, so no parser change is required.
- [x] `[Functional]` TUI rendering: Resolved by the existing splitter. Recognized titles become nodes; unknown titles merge into the previous node.

## Impact
1. `[EXTEND]` `MRP.md` — Replace Synthesis/Justification/Expectation/State Dashboard with Summary/Expectation/Progress/Notes and define Summary as the whole session story.
2. `[EXTEND]` `ALLOWED_RATIONALE_SECTIONS` — Add the four new titles while retaining the legacy titles for resumed plans.
3. `[MIGRATE]` `MarkdownPlanBuilder` and affected tests — Move fixtures and assertions to the new default rationale.
4. `[MIGRATE]` `plan-format.md` — Align the rationale format, replace the stale deprecated example actions, and reconcile *Code Block Nesting* with the MRP's tilde-and-backtick rule.
5. `[MIGRATE]` `debugger.md` — Rename `Synthesis Presentation` to `Summary Presentation`.
6. `[PRUNE]` Obsolete `Expected Outcome` rationale references — Remove the duplicate section name after migration. The legacy reviewer titles are retained deliberately, so they are not pruned.

## Deliverables
- [x] **Interface** - Lock the MRP rationale contract and extend `ALLOWED_RATIONALE_SECTIONS` additively. Landed in `f6126669` (four-section contract, additive allowlist, exact-list test) and consolidated in `e6631ed9` and `012e2f17`.
- [x] **Harness** - Update `MarkdownPlanBuilder` to emit Summary, Expectation, Progress, and Notes. Landed with its two default-binding test modules in one commit.
- [x] **Migration** - Update `plan-format.md`, `debugger.md`, the stale README sentence about synthesis/justification/expected outcomes, and every test fixture that pins the old rationale titles. Reconcile `plan-format.md`'s *Code Block Nesting* section with the MRP's tilde-and-backtick nesting rule. Landed as one change set: the spec and prompt pass plus eight inert fixture modules.
- [x] **Cleanup** - Remove obsolete `Expected Outcome` rationale references and keep legacy reviewer titles intentionally. No obsolete `Expected Outcome` rationale reference survived — every remaining occurrence is the protected `EXECUTE` parameter — so the residual scope was the `scripts/demo/` teaching fixtures, now migrated to the four-section vocabulary. The legacy reviewer titles stay by design.

## Implementation Notes
- The protocol text, the allowlist extension, and the exact-list test landed together in `f6126669`, so the atomic-commit constraint is discharged for those files. An unrecognized first section is dropped because `current_node` starts as `None`, so `MRP.md` must never be changed in a way that removes a title the allowlist accepts. The remaining spec, harness, fixture, prompt, and README changes may move in TDD-sized steps as long as `make test` stays green.
- `Summary` synthesizes the entire session story, not just the previous turn.
- Keep `Synthesis`, `Justification`, and `State Dashboard` in the reviewer allowlist so resumed sessions still render stored plans.
- The MRP action catalogs show the boolean toggles as `[true|false]` placeholders by an explicit product decision. Earlier revisions of `plan-format.md` stated the emitted value MUST be enclosed in backticks; that mandate was wrong and has been removed, and the behaviour that actually holds is recorded under Parameter Values in the same spec. The placeholders are notation-only.
- The Harness flip moved as one commit with the two modules that bind the builder's default: `MarkdownPlanBuilder` now emits `### Summary`, `### Expectation`, `### Progress`, and `### Notes`, and `test_plan_builder.py` plus `test_tui_rationale_parsing.py` follow it. The mixed-format acceptance case now injects its own legacy-plus-protocol rationale through `with_rationale` instead of post-processing the default, so it still pins mixed-heading parsing without binding the builder. Because `Expected Outcome` is not an allowlist title, a stored legacy rationale renders that section's content inside the preceding node rather than dropping it.
- Migration landed as one change set across two passes. The documentation pass rewrote `plan-format.md`'s rationale format block to the four `###` sections with a whole-session-story Summary, replaced the comprehensive example's legacy rationale, deleted its deprecated `PROMPT`/`INVOKE` tail, and reconciled *Code Block Nesting* to the MRP's rule (either fence character; the fence must be strictly longer than the longest run of the same character inside the content). It also renamed `debugger.md`'s step `Synthesis Presentation` → `Summary Presentation` and updated the stale `README.md` sentence. The fixture pass renamed the legacy vocabulary in eight inert modules: `test_tui_instruction_bridge.py`, `test_resilient_edit_matching_integration.py`, `test_validation_diagnostics_integration.py`, `test_parser_create_overwrite.py`, `test_parser_path_retention.py`, `test_tui_rationale_scrolling.py`, `test_markdown_plan_parser_session.py`, and `test_normalize_h1.py`. No test asserts on rationale text, so the rename is behavior-preserving: the touched modules reported 28 passed and the full suite stayed green at 2274 passed / 5 skipped.
- Deliberately untouched: `test_section_filtering.py` pins the legacy allowlist, and `test_rationale_filtering.py` keeps the legacy-rendering edge case because new-vocabulary rendering is already pinned by `test_tui_parses_default_rationale_sections`. The reviewer allowlist itself keeps the three legacy names so resumed sessions still render stored plans.
- Every remaining `Expected Outcome` occurrence is the `EXECUTE` action parameter — the parser mapping, the report template, the MRP action catalog, the builder default, and their fixtures — which the slice explicitly protects. The only user-visible carrier still on the old rationale vocabulary is `scripts/demo/`: three plan files plus the `drive.py` navigation comments. No test reads them, so Cleanup migrates them as its residual scope.
- Cleanup migrated the residual `scripts/demo/` carriers. The three plan fixtures were rewritten semantically, not mechanically: the old `Justification` prose now sits under `Summary`, the old `Expectation` prose under `Expectation`, and the `State Dashboard` goal block under `Progress`, so each section still teaches its concept. `drive.py`'s four navigation comments were renamed in one pass. No product code or test changed; `scripts/demo/` has zero coverage, so the suite stayed green at 2274 passed / 5 skipped and the vocabulary audit confirms the only surviving legacy tokens are the reviewer allowlist and the two protected test modules.
- The `Expected Outcome` half of Cleanup was a no-op by design: the token audit shows every surviving occurrence is the `EXECUTE` action parameter, which the slice explicitly protects. The reviewer allowlist deliberately keeps `Synthesis`, `Justification`, and `State Dashboard` so resumed sessions still render stored plans.
- Staging `scripts/demo/drive.py` surfaced two pre-existing lint findings: `C901` (`main` complexity 11 > 9) and `PLR0915` (99 statements > 40). The file is a single linear pexpect recording script with no test coverage, so splitting `main()` risks a timing regression the suite cannot catch. It is scoped off through a `[tool.ruff.lint.per-file-ignores]` entry with a reason comment rather than a file-wide or inline bypass; remediation stays with the Milestone 5 quality-gate work.
- Slice completion audited at `ab0d15d2`. No skeleton response or hardcoded stub was introduced: the four-section vocabulary reaches the reviewer through `ALLOWED_RATIONALE_SECTIONS` and the migrated `MRP.md`, both of which derive from the locked contract. `src/` carries no legacy rationale token outside that allowlist, and the reviewer component doc already describes the dual-format rationale parser without enumerating section names, so no as-built edit was required. `make test` stayed green at 2274 passed / 5 skipped.
- The allowlist and the parser were later narrowed on direct user order, superseding the legacy-retention decision recorded above. `ALLOWED_RATIONALE_SECTIONS` now holds only `Summary`, `Expectation`, `Progress`, and `Notes`; `handle_mount_logic` splits on `\n(?=### )` and strips only the `### ` marker, so a numeric `1. Section` marker is body text that merges into the preceding node. The nested `PROGRESS:` label was removed from `MRP.md`, `plan-format.md`, and the three demo plans, and `plan-format.md` now states that only the four `###` headings delimit sections. The reviewer invariant `rationale_dual_format` became `rationale_heading_only`, the numeric-marker module `test_rationale_filtering.py` was deleted as obsolete, and `test_tui_parses_mixed_rationale_sections` became `test_tui_only_accepts_markdown_headings`. `make test` stayed green at 2273 passed / 5 skipped, one test fewer because of the deletion.
- The last outlier was the harness default. `MarkdownPlanBuilder` emitted the pre-protocol Progress body (`**Vertical Slice:**` / `**Development Workflow:**` / `**Active Phase Details:**`), which `test_plan_builder.py` pinned twice. It now emits `Goal:` and `Reference Files:` followed by the phase checklist, matching `MRP.md` and `plan-format.md`, so the spec, the protocol, and the harness describe one Progress shape. Only fixtures changed; `make test` stayed green at 2273 passed / 5 skipped.

## Verification
1. **Protocol wording:**
   Run `teddy get-prompt pathfinder`.
   Verify the response protocol contains `### Summary`, `### Expectation`, `### Progress`, and `### Notes`.
2. **Reviewer rendering:**
   Start `teddy start` with a plan using the four sections.
   Open the Rationale tree.
   Confirm four sibling nodes appear and each opens its own content.
3. **Legacy rendering:**
   Resume a session whose stored plan uses `Synthesis`, `Justification`, `Expectation`, and `State Dashboard`.
   Open the Rationale tree.
   Confirm no legacy node appears: the leading `Synthesis` section is dropped, and each later legacy section's content is appended to the preceding accepted node.
