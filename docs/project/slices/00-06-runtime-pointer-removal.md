# Slice: Remove the Runtime Pointer Row from the Payload Header
- **Status:** Planned
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

- [ ] **Interface** - Revise the spec's `System Information` and `Runtime` sections and the design doc's `runtime_closes_payload` invariant to describe a header of CWD, OS, and Shell only, and drop the `_format_header` docstring clause naming the row.
- [ ] **Core** - Remove the pointer row from `ContextService._format_header` and reframe the two unit header assertions as guards against its return, keeping the `## Runtime` placement assertions unchanged.
- [ ] **Migration** - Update the acceptance tracer's ordering assertion and comment to match a header that no longer mentions the section.

## Implementation Notes

## Verification
1. **Session payload header:**
   From a session turn directory under `.teddy/sessions/<name>/`, run `teddy context --no-copy`.
   Verify `## System Information` lists CWD, OS, and Shell only, with no row naming `## Runtime`, and that `## Runtime` still closes the payload.
2. **Session-agnostic export:**
   Run `teddy context --only -c README.md --no-copy`.
   Verify the header ends at the Shell row and the payload still ends with the three `## Runtime` rows.
