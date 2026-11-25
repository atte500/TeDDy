# Slice: Remove the Runtime Pointer Row from the Payload Header
- **Status:** Completed
- **Milestone:** —
- **Depends On:** —
- **Specs:** [context-payload-format](../specs/context-payload-format.md)
- **Prototype:** —
- **Component Docs:** [ContextService](../../architecture/core/services/context_service.md)
- **Scope Slug:** `runtime-pointer`

## Goal
The payload header spends one row restating where the `## Runtime` section lives instead of stating an environment fact. Removing it leaves a header of pure environment details, so an agent reading `input.md` meets each fact exactly once.

## Context
- `ContextService._format_header`: emits `# Project Context`, `## System Information`, then one row per environment fact (CWD, OS, Shell) closed by a `- **Runtime:**` row pointing at the payload tail. Its docstring names that closing row. `get_context` appends the real `## Runtime` section with the three volatile rows after `_format_content` returns, so the pointer row is the only mention of the section inside the byte-stable prefix.
- `get_context` call paths: `format_project_context` feeds the `teddy context` export and `PlanningService.generate_plan` feeds `input.md`. Both consume the same header, so both shed the row together; session mode and the session-agnostic export both shed it, because the header renders unconditionally.
- Prefix caching: the removed row was byte-stable, so consecutive payloads still share an identical prefix up to the volatile tail. The change shortens the header without moving the first differing byte.
- `docs/project/specs/context-payload-format.md`: the `System Information` section pins the row in its prose, its rows list, and its example block; the `Runtime` section justifies it as the signpost that made the relocation legible.
- `docs/architecture/core/services/context_service.md`: the `runtime_closes_payload` invariant names the pointer row as the header's closing element.
- Test harness: the unit suite pins the row twice, in the header-shape test and in the Runtime-placement test. The acceptance tracer carries a comment explaining that it anchors on the heading line because the header collides with the literal `## Runtime`. No golden payload fixture and no whole-header string comparison exists.

## Scenarios

> As an agent reading `input.md`, I want each environment fact stated once so that a restatement of the payload's structure never reads as a fact.

```gherkin
Given a session turn directory in scope
When the payload is assembled for the next turn
Then `## System Information` lists CWD, OS, and Shell with no row naming the `## Runtime` section
And `## Runtime` is still the payload's final section carrying Current Date, Current Time, and Current Turn
```

```gherkin
Given `teddy context` exports a payload with no session root in scope
When the payload is assembled
Then the header carries no row naming the `## Runtime` section
And `## Runtime` still closes the payload with the three volatile rows
```

## Edge Cases
- **No literal collision:** The header must not contain the text `## Runtime` in any form, because a text search for the heading must reach the real section first.
- **Volatile values stay at the tail:** Current Date, Current Time, and Current Turn must not return to the header; this change alters discoverability only, never placement.
- **Header row set:** `## System Information` carries exactly CWD, OS, and Shell, with no empty row or trailing separator left behind by the removal.
- **Session-agnostic parity:** A payload with no session root keeps rendering `## Runtime`, because date, time, and turn exist without a session.
- **Token accounting:** The header's token contribution drops by one row. No assertion may pin a literal payload or header total that assumed the removed row.

## Key Unknowns

None. Every affected surface is settled by code reading: the row is one independent list element, the two unit assertions and the acceptance comment are the only test-side references, and no fixture compares the whole header.

## Impact
1. `[MIGRATE]` `ContextService._format_header` — drop the closing pointer row and the docstring clause naming it, so the header ends at the Shell row.
2. `[MIGRATE]` `docs/project/specs/context-payload-format.md` — rewrite the `System Information` prose, rows list, and example block, and rewrite the `Runtime` sentence that justifies the signpost.
3. `[MIGRATE]` `docs/architecture/core/services/context_service.md` — restate `runtime_closes_payload` without the pointer row.
4. `[MIGRATE]` `tests/suites/unit/core/services/test_context_service.py` — turn both header assertions into guards that the row is gone, leaving the tail assertions untouched.
5. `[MIGRATE]` `tests/suites/acceptance/test_context_file_selection.py` — drop the comment explaining the now-absent collision and anchor the ordering assertion on the plain heading.
6. `[PRUNE]` The pointer row text itself.

Excluded surfaces: `docs/project/slices/00-03-payload-layout.md` is a completed historical record and keeps its account of introducing the row; `spikes/debug/pdf-context-utf8-decode/replica_context_service.py` is throwaway sandbox code outside every quality gate.

## Deliverables

- [x] **Interface** - Revise the spec's `System Information` and `Runtime` sections and the design doc's `runtime_closes_payload` invariant to describe a header of CWD, OS, and Shell only, and drop the `_format_header` docstring clause naming the row.
- [x] **Core** - Remove the pointer row from `ContextService._format_header` and reframe the two unit header assertions as guards against its return, keeping the `## Runtime` placement assertions unchanged.
- [x] **Migration** - Update the acceptance tracer's ordering assertion and comment to match a header that no longer mentions the section.

## Implementation Notes

- **Interface:** The contract now reads as a header of constant environment facts only. Four surfaces changed together: the spec's `System Information` prose dropped the paragraph justifying the signpost and its ordered rows list now ends at `Shell`; the spec's example block closes at the `- **Shell:**` row; the spec's `Runtime` section replaced the signpost justification with the plain statement that the header carries only constant environment facts, keeping its placement rationale and its every-mode coverage; the design doc's `runtime_closes_payload` now says `_format_header` emits only the constant environment rows; and the `_format_header` docstring reads "Formats the byte-stable header of constant environment facts."
- **Deliberate ordering:** The contract is declared before the code reaches it, so the code still emits the row while the docs describe its absence. The suite stayed green because the two unit assertions that still assert the row's presence sit in the Core deliverable, not this one.
- **Inherited traps for Core:** the two unit assertions pinning `- **Runtime:**` in `result.header` (header-shape test and Runtime-placement test) will fail the moment the row is removed, so they must flip in the same commit as the removal. The acceptance tracer's ordering anchor at `result.stdout.index("\n## Runtime")` currently survives only because the header row writes `## Runtime` inside backticks without the leading newline; once the row is gone the anchor must be re-derived from the plain heading.
- **Excluded surfaces confirmed untouched:** `docs/project/slices/00-03-payload-layout.md` keeps its historical account of introducing the row, and `spikes/debug/pdf-context-utf8-decode/replica_context_service.py` keeps its copy as throwaway sandbox code.
- **Core:** `_format_header` now joins `# Project Context`, `## System Information`, and the three environment rows, ending at `- **Shell:**`. The two list elements that built the pointer row are gone, so the header carries no `Runtime` token in either the row form or the heading form, and `get_context` still appends `## Runtime` plus the three volatile rows after `_format_content` returns.
- **Red before Green:** both unit assertions flipped first. The header-shape test's presence assertion became `assert "Runtime" not in result.header` plus `assert result.header.splitlines()[-1] == "- **Shell:** /bin/test"`, and the Runtime-placement test's pointer assertion became the same absence guard while its docstring lost the claim that the header keeps a pointer. Both failed against the emitting code with the row text quoted in the assertion diff, proving the guards bite rather than passing vacuously.
- **Edge-case coverage:** the absence guard covers *No literal collision*, because neither `- **Runtime:**` nor `## Runtime` can survive a header that carries no `Runtime` token at all; the final-line pin covers *Header row set*, because a leftover empty row or separator would displace the Shell row from last position. *Volatile values stay at the tail* and *Session-agnostic parity* hold by construction, since the append in `get_context` is untouched and renders regardless of session scope. *Token accounting* is unaffected because the count runs over the assembled `content` string, never over the header.
- **Integration:** the full suite passed (`2586 passed, 5 skipped`) with the acceptance tracer unmodified, so its `"\n## Runtime"` anchor now matches only the appended section. The Migration deliverable tightens that anchor and drops the stale comment without a red gate in between.
- **Grep result:** `git grep "Runtime:\*\*" -- src tests docs` returns no hit in `src/` or `tests/`; the surviving hits are the historical `00-03` slice and this slice's own Context and Traps prose. The acceptance test's comment is the only remaining stale test surface, and it belongs to Migration.
- **Migration:** the acceptance tracer now anchors on the plain `## Runtime` heading. The comment explaining the former collision is gone with the collision itself, so the ordering assertion reverts to the natural form and states what it means: `## Resource Contents` precedes the tail section. The module passed (`8 passed`) with the tightened anchor, which is the evidence that the assertion still measures the real heading rather than a header artefact. No production behaviour changed, so there was no Red step to drive; the tightened anchor proves itself by holding.
- **Grep exit codes:** `git grep` exits 1 when nothing matches, and the executor reports a non-zero first command as `FAILED_COMMAND` with no stdout, so a clean audit and a broken pattern looked identical in this slice's earlier reports. Both audits that appeared to fail were that exit code. Every later audit appends `|| echo none` so zero matches report as success.

## Verification
1. **Session payload header:**
   From a session turn directory under `.teddy/sessions/<name>/`, run `teddy context --no-copy`.
   Verify `## System Information` lists CWD, OS, and Shell only, with no row naming `## Runtime`, and that `## Runtime` still closes the payload.
2. **Session-agnostic export:**
   Run `teddy context --only -c README.md --no-copy`.
   Verify the header ends at the Shell row and the payload still ends with the three `## Runtime` rows.
