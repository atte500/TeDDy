# Slice: Payload Layout for Prefix Caching
- **Status:** In Progress
- **Milestone:** None (ad-hoc slice)
- **Depends On:** None
- **Specs:** [context-payload-format.md](/docs/project/specs/context-payload-format.md)
- **Prototype:** None required — every unknown was closed by measurement during discovery
- **Component Docs:** [context_service.md](/docs/architecture/core/services/context_service.md), [ARCHITECTURE.md](/docs/architecture/ARCHITECTURE.md)
- **Scope Slug:** `payload-layout`

## Goal
Reorder the context payload so the byte-stable prefix covers the session's stable documents and the whole prior history. Measured value: cached-input share rises from ~0.1% to a 60–80% average with a 20–35% floor, cutting input cost by 41–62% and prefill latency on 50–250KB prefixes.

## Context
- `ContextService.get_context` returns a `ProjectContext` whose `header` carries `## System Information` and whose `content` carries the remaining sections; `PlanningService._run_planning_phase` writes `f"{context.header}\n{context.content}"` to `input.md`.
- `ContextService._format_content` already receives `scoped_paths` keyed by scope (`Session` / `Turn`) and currently discards that keying when it emits a single `## Resource Contents` section at `context_service.py:470`.
- `is_own_session_path` is the existing predicate separating the session's own history from every other path; own history renders under `## Session History`, everything else under `## Resource Contents`.
- Measured on real payloads: the consecutive common prefix is ~96B and dies inside the volatile `- **Current Time:**` line. Deleting `- **Current Date:**`, `- **Current Time:**`, and `- **Current Turn:**` lifts the shared prefix to 23.3→51.1% (young session) and 31.1→38.6% (mature session). Hoisting non-history session-scoped resources lifts it to 80.0% / 60.2% average.
- Provider behaviour confirmed live on `openrouter/~deepseek/deepseek-flash-latest` (resolves to `deepseek/deepseek-v4.1-flash-1017`): automatic prefix caching with affinity preserved, `cached_tokens=2432` of `2454` on a repeated prefix, cache-read price 96.7% below the prompt price.
- `session.context` is not a clean stable set: it can contain own-session history artifacts (`initial_request.md`, `09/plan.md`, `09/report.md`). Those must stay inside `## Session History` in chronological order.
- `teddy context` runs with no session root, and the README contract states that an empty export carries no `Resource Contents` section.
- Exactly two assertions in `tests/suites/unit/core/services/test_context_service.py` (lines 398 and 473) pin the current section order.

## Scenarios
Primary user journeys and happy paths. These drive End-to-End Acceptance Tests in the Wiring deliverable.

> As a developer running a multi-turn session, I want the payload prefix to stay byte-identical between turns so the provider serves it from cache.

```gherkin
Given a session whose session.context lists README.md, docs/project/PROJECT.md and docs/architecture/ARCHITECTURE.md
And the upcoming turn's context references src/teddy_executor/core/services/context_service.py
When the payload for that turn is assembled
Then the payload renders `## Session Resources` before `## Session History`
And the three session documents appear only under `## Session Resources`
And the turn-scoped file appears only under `## Resource Contents`
```

```gherkin
Given any assembled payload
Then `- **Current Date:**`, `- **Current Time:**` and `- **Current Turn:**` appear under the final `## Runtime` section
And `## System Information` carries the static pointer row naming that section
And the first 1200 bytes of consecutive payloads are byte-identical
```

```gherkin
Given a session that has accumulated several turns of history
When two consecutive payloads are compared
Then every byte before the newest history entry is identical between them
```

## Edge Cases
Boundary conditions, errors, and validation edge cases. These drive granular Unit Tests in Core deliverables.

- **No session root:** a `teddy context` assembly keeps the single `## Resource Contents` section, because the hoist targets the session loop and the CHOP export contract names only `Resource Contents`.
- **Session-scoped own history:** a path that is both session-scoped and own-session history renders in `## Session History` only, because chronological ordering and the `### Initial Request` / `### Turn N` headers are pinned invariants.
- **Session context holds only history:** `## Session Resources` is omitted entirely, because an empty section is indistinguishable from an omission notice.
- **No resources at all:** both `## Session Resources` and `## Resource Contents` are omitted.
- **Path present in both scopes:** it renders under `## Session Resources` only, so the payload never duplicates content.
- **Declaration order:** the stable block follows `session.context` line order, giving the user a knob to order files by mutability.
- **Repository has no session resources but the turn read files:** `## Session Resources` is omitted while `## Resource Contents` renders.
- **Runtime placement:** `## Runtime` is the final section; rendering it earlier puts volatile bytes ahead of the append point and defeats the change.
- **Header legibility:** `## Runtime` holds exactly the three relocated key-value rows, nothing else, so the pointer row stays a truthful single-line signpost.

## Key Unknowns

- [x] [Functional] Discoverability of the relocated runtime fields: the agent must still locate Date/Time/Turn after they move to the payload tail. Design Sensitivity: resolved by a static pointer row in `System Information`; if that row proves insufficient in practice, the fields return to the header and the win drops back to the header-normalization figure alone.
- [x] [Harness] Observability of the partition: the decision depends only on the scope keys and the own-session-history predicate, both injectable through a `ProjectContext` value. Design Sensitivity: resolved; a fixture carrying one session-scoped non-history path, one session-scoped own-history path, and one turn-scoped path drives every branch, so no prototype is required.

## Impact
1. `[NEW]` `## Session Resources` — new payload section for non-history session-scoped files.
2. `[NEW]` `## Runtime` — new trailing payload section holding the three volatile environment fields.
3. `[EXTEND]` `ContextService._format_content` — additive assembly-order change; the signature already receives `scoped_paths` keyed by scope, so no contract break.
4. `[MIGRATE]` `tests/suites/unit/core/services/test_context_service.py` — the two order assertions and the `## Resource Contents` presence assertions move to the new layout.
5. `[MIGRATE]` `docs/project/specs/context-payload-format.md`, `docs/architecture/ARCHITECTURE.md`, `README.md` — the documented section set and the `Context Payload` / `Session Root` ubiquitous-language entries.

## Deliverables

- [x] **Interface** - Revise `docs/project/specs/context-payload-format.md` (section-order block, new `## Session Resources` and `## Runtime` sections, the static pointer row, the session-mode-only rule) and update the `Context Payload` and `Session Root` entries in `docs/architecture/ARCHITECTURE.md`.
- [x] **Harness** - Extend the context-service unit fixtures to build a `ProjectContext` with one session-scoped non-history path, one session-scoped own-history path, and one turn-scoped path, so the partition is observable without real session directories.
- [x] **Wiring** - Emit the `## Session Resources` heading and the trailing `## Runtime` section with today's content still entirely in `## Resource Contents`, proving the shape end-to-end before the partition lands.
- [x] **Core** - Implement the partition: in session mode only, session-scoped paths not admitted by `is_own_session_path` render in `## Session Resources` in `session.context` declaration order; relocate the three volatile fields out of `## System Information` into `## Runtime` and insert the static pointer row.
- [ ] **Migration** - Update the section-order assertions at `test_context_service.py:398` and `:473`, the `## Resource Contents` presence assertions, and every doc sentence naming the old layout (spec, README line 346, ARCHITECTURE).
- [ ] **Refactor** - Single-source the section order in one declaration instead of leaving it implied by call order, so a future section addition touches one place.

## Implementation Notes
The hoist is deliberately restricted to session mode. Reusing the existing `scoped_paths` keying keeps the change inside `_format_content`, and the exclusion of own-session history keeps `## Session History` chronological and header-shaped.

- **Interface (delivered):** the spec pins the section order and documents `## Session Resources` (declaration-order rendering, session-over-turn precedence, own-history exclusion, omission when nothing qualifies) and `## Runtime` (exactly the three volatile rows, rendered in every mode because date/time/turn exist without a session). `## System Information` closes with a static pointer row naming `## Runtime`, so the agent still finds the values after they leave the header while the row itself never varies between turns. The `Context Payload` and `Session Root` entries in `ARCHITECTURE.md` were rewritten to the same contract, so the ubiquitous language and the spec state one rule rather than two drifting descriptions.
- **Interface (migration consequence):** the spec's session-mode-only rule confirms the hoist must not touch the `teddy context` export path, so `_format_content` gains the new sections behind a session-root gate rather than unconditionally.
- **Harness (delivered):** `tests/harness/setup/context_scenarios.py` supplies the partition's three canonical paths without real session directories: `SESSION_DOCUMENT` (`docs/project/PROJECT.md`, session-scoped and not own-history, so it belongs in `## Session Resources`), `OWN_HISTORY_REQUEST` (`<root>/initial_request.md`, session-scoped own history, so it stays in `## Session History`), and `TURN_DOCUMENT` (a `src/` file under `Turn`, so it stays in `## Resource Contents`). `tests/suites/unit/test_context_scenarios_harness.py` pins the contract and asserts each path drives exactly one branch, so a future predicate change breaks the harness test rather than silently weakening the partition test.
- **Harness (builder constraint):** `context_scenario()` always emits both `Session` and `Turn` keys, because a falsy `context_files` mapping makes `_resolve_scoped_paths` fall back to the default vault paths. An empty scenario therefore reads `{"Session": [], "Turn": []}` rather than `{}`. Scope lists are never sorted, so `session.context` declaration order remains the user's mutability knob.
- **Harness (shape):** the deliverable shipped as a data-only scenario module consumed by context-service tests, not as an extension of the `service` fixture. The module imports no context-service code, matching the `EditScenarios` convention, so a test cannot couple to the implementation it exercises.
- **Wiring (delivered):** `_format_content` prepends `## Session Resources` behind the existing `session_root` gate and appends `## Runtime` as the document's final section. Every resource still renders under `## Resource Contents`, and the three volatile rows stay in `## System Information` until Core. Tail placement is load-bearing rather than stylistic: both assembly paths — `format_project_context` for the `teddy context` export and `PlanningService.generate_plan` for `input.md` — join `header + "\n" + content`, so only the last bytes of `content` reach the document's end.
- **Wiring (tracer bullet):** `test_session_payload_carries_session_resources_and_runtime_sections` in `tests/suites/acceptance/test_context_file_selection.py` drives `teddy context` from a seeded turn directory carrying `turn.context`, `session.context`, and `meta.yaml`, because that is the one CLI surface threading a session root; the session-agnostic export can never observe these headings. The case asserts both headings and that `## Resource Contents` precedes `## Runtime`; it deliberately does not assert where content lands, since Core owns the partition.
- **Wiring (gate discovery):** `detect_session_root()` resolves `Path.cwd().parent` when the three gate files exist and `None` otherwise, so `teddy context` run from a turn directory already enters session mode. That made a full `teddy start` with a mocked LLM unnecessary for the tracer bullet.
- **Wiring (empty heading):** until Core partitions content, `## Session Resources` renders empty in session mode. The slice's omission rule (never render the heading with nothing under it) therefore lands in Core, not Wiring; the acceptance seed's `session.context` lists `README.md`, a session-scoped non-history path, so the heading survives that omission rule when Core applies it.
- **Core (partition):** `_partition_paths` splits the resolved paths into session resources, own history, and turn resources. It collects every non-`Turn` scope first and then `Turn`, skipping any path already seen, so a path listed in both scopes renders once; that collection order is what enforces session-over-turn precedence. Own history goes to Session History whatever its scope, Session Resources exist only when a session root is in scope, and the remainder falls to `## Resource Contents`.
- **Core (rendering):** `_format_file_section` generalizes the former workspace renderer to any heading, so Resource Contents and Session Resources cannot drift apart in fence sizing, link form, or file-not-found handling. An empty path list returns nothing, which is exactly what satisfies both omission rules — no resources at all, and a session context holding only history.
- **Core (Runtime placement):** `get_context` appends `## Runtime` and the three volatile rows after `_format_content` returns, and `_format_header` now emits only CWD/OS/Shell plus the static `- **Runtime:**` pointer row. Appending in `get_context` rather than inside `_format_content` keeps the section last in both assembly paths without the content formatter knowing about per-turn values.
- **Core (assertion repair):** the two cases that pinned the volatile rows moved from `result.header` to `result.content`, and the five new behavior cases read the canonical `MIXED_SCOPES` bundle rather than inventing paths. The Red run reported `7 failed, 17 passed`; the Green run reports the module plus the acceptance tracer green at 25 passed, and every order and presence assertion that predates the slice survived unchanged.
- **Core (literal collision):** the pointer row literally contains `` `## Runtime` ``, so any text search for the section heading matches the header first. The acceptance tracer therefore anchors its ordering assertion on `\n## Runtime`, which only the real heading line satisfies.

## Verification
1. **Session payload shape:**
   Run `teddy start -m "smoke check"`, approve the plan, then inspect `.teddy/sessions/<session>/02/input.md`.
   Verify `## Session Resources` appears before `## Session History`, and `## Runtime` is the final section holding the three date/time/turn rows.
2. **Prefix stability:**
   Run `head -c 1200 .teddy/sessions/<session>/01/input.md | shasum` and the same for `02/input.md`.
   Confirm both hashes match, proving the header is byte-stable across turns.
3. **CHOP export unchanged:**
   Run `teddy context --only -c README.md --no-copy`.
   Verify the output contains `## Resource Contents` and no `## Session Resources` heading.
