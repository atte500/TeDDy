# Slice: Pruning Policy by Cost of Loss
- **Status:** In Progress
- **Milestone:** None (ad-hoc)
- **Depends On:** None
- **Specs:** [context-payload-format](../specs/context-payload-format.md)
- **Prototype:** None
- **Component Docs:** [session_pruning_service.md](/docs/architecture/core/services/session_pruning_service.md), [config_service.md](/docs/architecture/core/ports/outbound/config_service.md)
- **Scope Slug:** `pruning-policy`

## Goal
Two changes to how `SessionPruningService` decides what leaves the turn-scope context. Delete `auto_pruning.prune_failure_history` and the heuristic it controls, so a turn that missed its expectation while gathering insight keeps its place instead of losing its `report.md` action log together with its `plan.md`. And order the global token budget's victims by what losing each file costs, so a restorable copy of a project file is deselected before an irreplaceable turn record.

## Context
- `SessionPruningService.prune`: runs the status heuristics first, then the retention ceiling, then the global token budget, on every session turn. Of the status heuristics this slice touches only the plan-status one, leaving validation pruning intact, and it separately reorders the global budget's victims as described further below.
- The heuristic is a chain of four members, not one branch: `_collect_turn_metadata` builds a `turn_statuses` mapping and returns it alongside `validation_failures` and `non_vf_reports`; `_update_metadata_from_plan` fills it through `_check_plan_failed`; `_apply_pruning_heuristics` reads it, behind the `prune_non_green` config read, to deselect non-green turns from `turn_statuses` once `current_status` is green or the latest on-disk turn is green, annotating each victim with `Pruned failure history after successful recovery`.
- `_check_plan_failed` reads a plan's `- **Status:**` line and treats any non-green turn as failed. That is why `🟡` — the protocol's "expectations not met, but new insight gathered", which an agent may hold indefinitely while it learns — is deselected exactly like `🔴`.
- `current_status` cannot be dropped with the heuristic: the validation branch inside `_apply_pruning_heuristics` still gates on it, so the parameter and its threading stay.
- Measured on the shipped layout (89 admitted pairs across 5 sessions): plan-status pruning owns 7 of 31 mid-history holes, validation pruning 12, the token budget 10, retention 2. Removing the heuristic therefore converts 7 holes into retained turns and leaves the other 24 untouched.
- Red is not the heuristic's live victim: `MRP.md` obliges every BLOCKED 🔴 turn to halt and emit a `## Message`, the service spares a plan carrying `## Message` with a `SUCCESS` report, and `preserve_message_turns` admits communicating turns to the prune-exempt session scope. The corpus confirms it 1 for 1 — 1 red plan, 1 messaged — against 120 amber plans of which 3 message. The amber turn is the only reachable target today.
- Config removal is behaviour-neutral on its own: `get_setting` falls back to the live merged mapping for an undeclared key, and the shipped `config.yaml` carries `prune_failure_history: true`, so the service keeps reading the old value until its predicate goes. That is what lets the Interface commit stand alone.
- `_check_report_is_success` and `_check_file_contains` have no caller anywhere in `src` or `tests`. They are dead independently of this deletion and sit in the file being cleaned.
- Harness: `tests/harness/setup/pruning_scenarios.py` models paths, token counts, git status and scope only, so no scenario can express a plan status. There is no Harness deliverable to write.
- Guardrail for implementation: confirm that `turn_statuses` feeds nothing but the recovery-cleanup branch before deleting it. If it also feeds a sparing rule, stop and report rather than working around it.
- `SessionPruningService._apply_global_budget`: runs after the status heuristics and the retention ceiling. It sums every selected `Turn`-scope item and, while the total exceeds `auto_pruning.turn_context_threshold`, deselects the largest remaining file, annotating it `Pruned to fit context budget`. The key is `token_count` descending and nothing else: no class is protected, and a `plan.md` is never coupled to its `report.md`.
- The two candidate classes differ in the one property that matters here: a turn record cannot come back, because nothing re-renders it and an agent has no signal telling it which pruned turn to `READ` again, while a copy of a project file returns with a single `READ` action.
- Measured by replaying the shipped `50000` threshold over every assembly that inherited a manifest (1457 assemblies, 463 over budget, production characters-over-four count): largest-first evicted a record in 194 of the 463, copies-before-records in 5, read-age order in 128 while deselecting 2306 files against 949, and class-then-age reached the same 5 record-hits as class alone for 2205 victims.
- Dropping copies alone, largest first, brings 457 of the 463 assemblies at or under the threshold, so the copy pool usually absorbs the whole overage. The remaining 5 cannot be satisfied without a record, which is why the fallback drops whole turns rather than capping record loss: a cap would leave those 5 over budget with nothing left to drop.
- Read age is not recorded anywhere. `turn.context` is written as `"\n".join(sorted(list(paths)))`, so gather order is destroyed before the manifest is persisted, and no `ContextItem` field carries a timestamp; ranking by recency would need new persisted state inside a file that is itself part of the payload.
- The whole-turn fallback needs no new state: `_extract_turn_id` already returns the last numeric directory segment of a path, and `_map_turn_ids` maps item indices onto those ids.
- Session-scope paths never enter the budget: `ContextService` upgrades a `Turn` path to a `Session` one on dedup, and the budget sums only `scope == "Turn"`.
- Depth belongs to retention (`max_turns_retention`, `retention_batch`); the budget owns bytes only. The two measured populations stay apart — 463 over-budget assemblies for victim policy, 89 admitted payload pairs for holes — and are never combined into one rate.
- Cache cost of the shipped rule: a mid-history removal ends the shared prefix at that turn's position instead of at the append point, and the budget owns 10 of the 31 mid-history holes measured on the shipped layout.

## Scenarios

> As a developer resuming work after an exploratory turn, I want that turn's plan and report to stay in context, so that findings already verified survive instead of being re-derived from a paraphrase.

```gherkin
Given a session whose turn 4 plan is OFF-TRACK 🟡 with a SUCCESS report
And a later turn returns ON-TRACK 🟢
When the next context payload is assembled
Then turn 4's plan and report still render under ## Session History
And neither carries an auto-prune reason
```

```gherkin
Given a session whose turn 6 report is Validation Failed
And a later turn succeeds with a non-validation report
When the next context payload is assembled
Then turn 6 is deselected with the reason Plan failed validation
```

```gherkin
Given a project config that still sets auto_pruning.prune_failure_history to false
When a session prunes its context
Then the setting is ignored without an error
And no turn is deselected for being non-green
```

> As a session whose working context exceeds the token budget, I want a file I can re-read to leave before a turn record I cannot, so that no reasoning trail disappears while a restorable copy is kept.

```gherkin
Given a turn-scope set over the budget that holds three copies and two turn records
And the largest selected file is a copy
When the budget deselects victims
Then that copy leaves first
And both turn records keep their plan and report rendered
```

```gherkin
Given a turn-scope set over the budget whose records alone exceed the threshold
When the budget deselects victims
Then the oldest retained turn leaves with its plan and report together
And no turn renders a plan without its report
```

## Edge Cases
- **Amber plan, successful report:** stays selected after a later green turn, because the heuristic that removed it no longer exists. This is the case the corpus measures.
- **Amber plan whose report failed validation:** still removed by validation pruning once a later non-validation turn succeeds. The two heuristics overlapped on such a turn and only the validation one keeps its behaviour, so the deletion must not also disable that branch.
- **Red plan:** unchanged. It is a communicating turn, spared by the message rule and pinned into the session scope, so the deletion does not make it newly prunable.
- **Stale config key:** an unknown nested key is dropped silently at config construction, so a user who set the key keeps a dead line in their `config.yaml` with no error and no warning. Anyone who set it to `false` did so to stop failures being pruned, which the new behaviour matches, so no migration note is required.
- **`_collect_turn_metadata` return shape:** losing the `statuses` key changes the mapping's shape. Every reader lives inside the service, so the shrink stays internal; assert the two survivors keep their keys and semantics.
- **Retention and budget separated:** after the deletion a corpus census should still show validation, retention and budget holes and no plan-status holes. A census that loses more than the plan-status share indicates an over-deletion.
- **Pair granularity overshoot:** when copies cannot cover the deficit, a whole turn leaves at once, so a small deficit can deselect a pair larger than the shortfall. The total then undershoots the threshold, which still satisfies the ceiling; this path covers 5 of the 463 measured over-budget assemblies.
- **Record classification:** a path counts as a record only when its filename is `plan.md` or `report.md` and it sits under a numeric turn directory of the session root. A project file that happens to be named `plan.md` elsewhere stays a copy.
- **A turn holding only one of its two records:** a recorded manifest can carry `08/report.md` with no `08/plan.md`. The fallback therefore drops whichever of the pair the turn actually holds and never asserts that both exist, so the invariant it enforces is that a plan and its report never part company when both are present, never that every turn carries two files.
- **Path with no turn id:** a turn-scope path whose id cannot be derived cannot be paired, so the fallback treats it as a single-file turn rather than dragging an unrelated turn out with it.
- **Under the threshold:** the ordering code never runs, so behaviour stays byte-identical for the roughly two thirds of measured assemblies that stay within the budget.
- **Equal sizes:** Python's `sorted` is stable, so two equally large files keep their manifest-relative order; a test asserting an alphabetical tiebreak would encode behaviour the sort does not have.

## Key Unknowns
None. Every remaining question is answerable by reading the service body, and the four members of the chain have already been read.

## Impact
1. `[PRUNE]` `ConfigSchema.AutoPruningConfig.prune_failure_history` and its `_SCHEMA_FIELDS` entry — the key stops being declared.
2. `[PRUNE]` `src/teddy_executor/resources/config/config.yaml` — the shipped `prune_failure_history` line and its trailing comment.
3. `[PRUNE]` `SessionPruningService` heuristic chain — the `prune_non_green` config read, the `turn_statuses` collection, `_update_metadata_from_plan`, `_check_plan_failed`, and the recovery-cleanup branch that writes `Pruned failure history after successful recovery`.
4. `[EXTEND]` `SessionPruningService._apply_global_budget` — replace the single `token_count`-descending key with a lexicographic one, copies before records and largest-first inside each class, and add the whole-turn fallback that deselects the oldest retained turn's plan and report together once no copy remains. The signature and the `Pruned to fit context budget` reason stay unchanged.
5. `[EXTEND]` `SessionPruningService` — one predicate classifying a turn-scope path as record or copy, built from the filename plus the turn id `_extract_turn_id` already derives, so no new persisted state is written.
6. `[MIGRATE]` `SessionPruningService._collect_turn_metadata` and `_apply_pruning_heuristics` — drop the status collection from the returned mapping and the parameter that carries it, keeping `current_status` for the validation branch.
7. `[PRUNE]` `SessionPruningService._check_report_is_success` and `_check_file_contains` — dead before this slice, removed here because they live in the file being cleaned.
8. `[MIGRATE]` the affected status-pruning test modules — `test_session_orchestrator_pruning.py` (retire `test_execute_prunes_failure_history_heuristic`), `test_session_pruning_service_refinement.py` (retire the recovery-cleanup cases), `test_session_pruning_status_anchoring.py`, `test_session_pruning_robustness.py`, `test_session_pruning_retention_window.py`, `test_session_primary_path_pruning.py`, `test_session_pruning_windows.py` (drop the dead config-double key and any reason-string assertion), `test_validation_failure_pruning_timing_integration.py` (drop the three isolating `False` entries), `test_yaml_config_adapter.py` (drop the assertion that reads the key from the bundled config), and `test_context_management_ui.py` (rewrite the two acceptance cases around the surviving behaviour).
9. `[MIGRATE]` the budget-ordering tests — locate every case pinning the current largest-first sequence by searching for the `Pruned to fit context budget` reason, then restate its expected victims in class-then-size order and add the whole-turn fallback cases.
10. `[MIGRATE]` documentation surfaces — the `IConfigService` key table, the heuristics list in `session_pruning_service.md` (whose `Global budget` bullet must state the class-then-size order and the whole-turn fallback), and the census bullet in `context-payload-format.md`, which must keep its measurement while noting that only validation and budget removal remain live.

## Deliverables
- [x] **Interface** - Remove `prune_failure_history` from `AutoPruningConfig`, its `_SCHEMA_FIELDS` entry, and the shipped `config.yaml` line with its comment; drop the key from the `IConfigService` table and delete the adapter test assertion that reads it. Behaviour is unchanged at this commit: the merged mapping still supplies `true`, so the service reads the same value through the fallback path.
- [x] **Core** - Delete the heuristic chain and retire the unit and integration cases that pin it in one commit, so the suite stays green at every step: the recovery-cleanup branch, the `prune_non_green` read, `turn_statuses`, `_update_metadata_from_plan`, `_check_plan_failed`, and the `statuses` key plus `turn_statuses` parameter. Keep `current_status` threading for validation pruning. Update the heuristics list in `session_pruning_service.md` and the spec's census bullet in the same commit, so no document describes a mechanism the code no longer has.
- [x] **Core** - Order the budget's victims by cost of loss: classify a turn-scope path as record or copy, rank copies before records and largest-first inside each class, and drop the oldest retained turn's records together once no copy remains. Carry the ordering's unit cases in the same commit — a copy leaves before a larger record, whole turns leave oldest first when copies run out, a turn's plan and report leave together whenever both are present, a turn holding only one record drops just that one, a project file named `plan.md` outside a turn directory stays a copy, and equal sizes keep manifest order — and update the `Global budget` bullet in `session_pruning_service.md`.
- [x] **Migration** - Drive both behaviours through the outermost boundary: the two acceptance cases in `test_context_management_ui.py` become "an amber turn survives recovery" and "a validation-failed turn is still pruned"; an over-budget assembly keeps its newest record and drops a larger copy instead; and every pruning config double across the suites loses the dead key.
- [ ] **Cleanup** - Remove `_check_report_is_success` and `_check_file_contains`, which have no caller in `src` or `tests`. If implementation finds a dynamic caller, drop this deliverable and record the finding rather than preserving dead code around it.

## Implementation Notes

### Interface — retiring the plan-status key

The key stopped being declared in one commit, across four surfaces plus one test:

- `AutoPruningConfig` lost the field and `_SCHEMA_FIELDS` lost its `_FieldSpec`, so `is_declared_key` now reports `False` and `construct_app_config` ignores a user value instead of coercing it.
- `src/teddy_executor/resources/config/config.yaml` lost the shipped line and its trailing comment.
- The `IConfigService` key table lost its row. This was not optional: `test_documentation_and_schema_declare_the_same_keys` fails the moment the schema drops a key the document still lists, so the drift closure is what makes the removal contractual rather than a silent deletion.
- `test_auto_pruning_defaults_are_present` lost the single assertion reading the key from the bundled file; its four remaining `auto_pruning` assertions stayed.
- A positive contract test, `test_retired_plan_status_key_is_no_longer_declared`, pins the absence through the public `is_declared_key` seam plus the `AutoPruningConfig` field set. It failed first with `assert not True` against the still-declared key.

Behaviour is unchanged at this commit, as the slice required. `SessionPruningService` still calls `get_setting("auto_pruning.prune_failure_history", True)`, and with the key undeclared and absent from the shipped baseline that call resolves the call-site default `True`, the same value the baseline supplied. A test double that still sets the key keeps exercising the live merged mapping for an undeclared key, so an explicit `False` still reaches the service. Full suite after the change: 2619 passed, 5 skipped.

Discovery corrected one assumption in the slice's Impact section: `test_config_schema.py` already owned both `is_declared_key` and the documentation drift closure, so the Red test needed no new machinery beyond a `dataclasses` import and the `AutoPruningConfig` type.

### Core — deleting the plan-status heuristic chain

The guardrail was resolved by grep before any deletion. `turn_statuses` appeared only inside the chain itself (`_identify_turns_to_prune` → `_collect_turn_metadata` → the two metadata helpers → the recovery-cleanup branch). `preserve_message_turns` is read in `session_service.py` at two sites — message sparing lives in context admission, never in this service — so the stop-and-report condition never triggered.

Deleted from `SessionPruningService`: the `prune_non_green` config read, the `turn_statuses` collection and its `statuses`/`non_green` keys in the shared state map, `_check_plan_failed`, `_update_metadata_from_plan` and the two routing helpers it introduced (`_update_metadata_from_report`, `_update_turn_metadata_from_item`), and the recovery-cleanup branch with its `Pruned failure history after successful recovery` reason. `_collect_turn_metadata` now returns `(validation_failures, non_vf_reports)` and `_apply_pruning_heuristics` takes only those three surviving parameters, so `current_status` threading stays because the validation branch still gates on it. Because those routing helpers only existed to feed the status map, folding their report-only work back into `_collect_turn_metadata` kept the file honest.

Red was `test_amber_plan_survives_a_later_green_turn`, failing at `assert [False, False] == [True, True]` with the recovery-cleanup branches deselecting both records of an `OFF-TRACK 🟡` turn whose report succeeded.

Two findings corrected earlier notes:

- The `str(int(turn_id))` lookup in `_process_context_item` is **load-bearing**, not vestigial. `_extract_turn_id` returns literal digits, so a padded `01/` directory only meets the producers' `"1"` key through that normalisation. It was collapsed from a double lookup into one normalised call rather than dropped.
- The acceptance restatement could not wait for the Migration deliverable: deleting the chain turned `test_auto_pruning_heuristics_acceptance` red, so the slice's keep-the-suite-green rule pulled that migration into this commit.

Test surface, all in the same commit:

- `test_session_pruning_status_anchoring.py` — the two plan-status cases (`test_prune_ignores_emoji_in_rationale`, which became vacuous, and `test_prune_targets_anchored_status_failure`, which asserted the retired reason) collapsed into the amber-survival case.
- `test_session_pruning_robustness.py` — both cases were pure recovery cleanup, so they were restated through validation pruning, which keeps the two invariants they were written to protect: a zero-padded turn directory (`01/` meeting the `"1"` key) and a four-digit year segment not mistaken for a turn id.
- `test_session_pruning_windows.py` — the backslash case restated through validation pruning, keeping the Windows path invariant, and asserting that a failed turn's plan and report leave together.
- `test_session_pruning_service_refinement.py` — `test_prune_triggers_recovery_cleanup_via_current_status` retired; the budget, threshold-fallback and initial-request cases untouched.
- `test_session_orchestrator_pruning.py` — `test_execute_prunes_failure_history_heuristic` retired, and the fixture lost both `prune_failure_history` and the never-declared `prune_preceding_on_non_green`.
- `test_context_management_ui.py` — `test_auto_pruning_heuristics_acceptance` now asserts the slice's scenario, with the fixture corrected to an honest amber turn (off-track plan, `SUCCESS` report) and `02/report.md` admitted to the manifest so both surviving records are observable; the sibling TUI case stopped passing a reason string production can no longer emit.

Documentation landed in the same commit. `session_pruning_service.md` lost the recovery-cleanup bullet and had its Purpose, dependency line and `prune` postconditions narrowed to validation pruning. The spec's census bullet keeps its measured `12 + 10 + 7 + 2 = 31` breakdown and states the plan-status share is historical, because the numbers are the evidence for the deletion. Full suite: 2616 passed, 5 skipped — the pre-deletion 2619 minus the two retired cases and the net one from collapsing the status pair.

### Core — ordering budget victims by cost of loss

Victim selection moved from one size-descending sort to a two-class order, built entirely from state the service already carried. `_record_turn_id` classifies a path as a record when its filename is `plan.md` or `report.md` and `_extract_turn_id` finds a numeric directory segment, so `docs/plan.md` stays a copy without ever comparing against a session root that `_apply_global_budget` does not receive. `_rank_budget_candidates` returns copies sorted largest-first — a tie keeps manifest order because `sorted` is stable — and records grouped under their turn id, which `_apply_global_budget` then drops turn by turn in `sorted(turns)` order, oldest first.

The fallback's loop order is the load-bearing detail: sorting records by size instead would drop the newest turn before the oldest and fail the oldest-first invariant, so turns are ordered by id and only copies are ordered by size.

Three consolidations arrived with the ordering, each exposed by writing the Red cases first: the candidate predicate copied three times became `_iter_budget_candidates`, the twice-written reason literal became `_BUDGET_PRUNE_REASON`, and the record filenames became `_RECORD_FILENAMES`. `_map_turn_ids` was left untouched, because retention counts distinct turn ids and has no stake in the classification.

Red was five of six cases failing against the shipped sort and the equal-size tiebreak passing, which was the predicted split and proved the gap behavioural: the 400-token copy survived while the 900-token plan left, the 500-token `docs/plan.md` left while a record stayed, and a turn's report survived its own plan being dropped. Green passed all six with no production logic beyond the classifier and the two loops, and the seven sibling budget-facing modules stayed green (38 passed), confirming the reordering inverted no shipped expectation.

Discovery settled why that was so, and it is worth recording: no existing case pinned a record-before-copy expectation. The orchestrator case (`large.py`/`medium.py`/`small.py`) and the primary-path case (`big1.py`/`big2.py`) use copy-shaped paths that remain the first victims, and both refinement budget cases hold only records, so they land in the whole-turn fallback and drop the same single file they always dropped. The retention-window module arms `turn_context_threshold: 0`, so the budget never runs there.

Documentation landed in the same commit. `session_pruning_service.md` gained the class-then-size order and the whole-turn fallback in its `Global budget` bullet plus a `record_pair_integrity` class invariant, so pair integrity is stated where the other invariants are. Two spec bullets were corrected rather than merely touched: the census bullet still claimed the budget drops the largest files, and the ordering bullet still described a `token_count`-descending sort. Both now say class first, token count second.

Full suite: 2622 passed, 5 skipped — the previous gate's 2616 plus the six ordering cases.

### Migration — driving the budget through the acceptance boundary

The budget had never been observed through the outermost entry point, and the blocker was arithmetic rather than wiring: `TestEnvironment._apply_llm_defaults` pins `get_text_token_count` to `0`, so every assembled item weighed nothing and no assembly could exceed a threshold. The case supplies a counter proportional to content length with `env.get_service(ILlmClient).get_text_token_count.side_effect = lambda text, model=None: len(text)`. That is substitution through the resolved port the composition already injected, so the counter arrives by constructor injection and no module is patched. `src/huge_module.py` (600 lines) then outweighs the four records it travels with, and a threshold of 3000 sits above the records' combined weight, so evicting the copy alone brings the assembly under budget.

Two fixture defects surfaced during the Red step, and both were real rather than incidental:

- The resumed plan reads `README.md`, which the fixture never created, so pre-flight validation failed. Because the test `ISessionLoopGuard` allows exactly one planning turn, that failure consumed the run and plan review was never reached — the symptom was `review` called 0 times, not a pruning error. Writing `README.md` fixed it.
- A threshold of 1000 was too low: the copy could not cover the whole overage, so the whole-turn fallback would have legitimately evicted turn 01's records and contradicted the assertion the case exists to protect. Raising it to 3000 made the copy sufficient on its own.

The case's evidential limit is worth stating plainly rather than overclaiming: because the copy is also the largest item, this assembly cannot distinguish the class-then-size order from the retired size-only sort. It proves the budget runs at all through the CLI boundary and that a restorable copy absorbs the overage instead of a record. The six unit cases in `test_session_pruning_budget_ordering.py` remain the only pin on the ordering itself.

The dead-key half of the migration finished across two turns. Turn 32 dropped it from the three unit double fixtures (`status_anchoring`, `primary_path`, `retention_window`); turn 33 stripped the three isolating `False` entries from the validation-failure timing integration module with an inline script that asserted an exact removal count of three, so a shifted file could not pass silently. Turn 32's attempt at the same script aborted on bare `python`, which does not exist on this machine; re-running it through `uv run python` is the project runner's correct invocation. The confirmation grep now finds the retired key only at `test_config_schema.py:265`, which is the positive contract test deliverable 1 added and must keep it.

Full suite: 2623 passed, 5 skipped — the previous gate's 2622 plus the acceptance case. The acceptance module reports 4 passed.

## Verification
1. **The schema no longer declares the key:**
   Run `uv run python -c "import dataclasses; from teddy_executor.core.domain.models.config_schema import AutoPruningConfig; print([f.name for f in dataclasses.fields(AutoPruningConfig)])"`.
   Verify the output contains `max_turns_retention` and `retention_batch` and does not contain `prune_failure_history`.
2. **Nothing in production names the key:**
   Run `git grep -n "prune_failure_history" -- src`.
   Verify the command prints no matches.
3. **An off-track turn survives recovery:**
   Resume a session that holds an amber turn followed by a later green turn with `teddy resume <session-slug>`.
   Open the newest `.teddy/sessions/<name>/NN/input.md` and confirm the amber turn's `### Turn N: Plan` header still renders under `## Session History`.
4. **Validation pruning still fires:**
   In a session whose turn took a `Validation Failed` report before a later successful turn, confirm that turn's headers are absent from the newest payload's `## Session History`, with the surrounding turns intact.
5. **The budget keeps a record over a larger copy:**
   Resume a session whose turn-scope load exceeds `auto_pruning.turn_context_threshold` and whose largest selected item is a project file. Confirm the newest payload still renders that turn's `### Turn N: Report` header while the project file is absent from `## Resource Contents`.
6. **Whole turns leave together:**
   In an assembly whose records alone exceed the threshold, confirm the oldest rendered turn is missing both its `### Turn N: Plan` and `### Turn N: Report` headers, never just one of the two.
