# Slice: Retire Plan-Status Failure Pruning
- **Status:** Planned
- **Milestone:** None (ad-hoc)
- **Depends On:** None
- **Specs:** [context-payload-format](../specs/context-payload-format.md)
- **Prototype:** None
- **Component Docs:** [session_pruning_service.md](/docs/architecture/core/services/session_pruning_service.md), [config_service.md](/docs/architecture/core/ports/outbound/config_service.md)
- **Scope Slug:** `failure-pruning`

## Goal
Delete `auto_pruning.prune_failure_history` and the heuristic it controls, so a turn that missed its expectation while gathering insight keeps its place in the agent's working context. Today such a turn loses its `report.md` action log together with its `plan.md`, and its successor inherits only a rewritten summary of conclusions.

## Context
- `SessionPruningService.prune`: runs the status heuristics first, then the retention ceiling, then the global token budget, on every session turn. This slice touches only the plan-status heuristic.
- The heuristic is a chain of four members, not one branch: `_collect_turn_metadata` builds a `turn_statuses` mapping and returns it alongside `validation_failures` and `non_vf_reports`; `_update_metadata_from_plan` fills it through `_check_plan_failed`; `_apply_pruning_heuristics` reads it, behind the `prune_non_green` config read, to deselect non-green turns from `turn_statuses` once `current_status` is green or the latest on-disk turn is green, annotating each victim with `Pruned failure history after successful recovery`.
- `_check_plan_failed` reads a plan's `- **Status:**` line and treats any non-green turn as failed. That is why `🟡` — the protocol's "expectations not met, but new insight gathered", which an agent may hold indefinitely while it learns — is deselected exactly like `🔴`.
- `current_status` cannot be dropped with the heuristic: the validation branch inside `_apply_pruning_heuristics` still gates on it, so the parameter and its threading stay.
- Measured on the shipped layout (89 admitted pairs across 5 sessions): plan-status pruning owns 7 of 31 mid-history holes, validation pruning 12, the token budget 10, retention 2. Removing the heuristic therefore converts 7 holes into retained turns and leaves the other 24 untouched.
- Red is not the heuristic's live victim: `MRP.md` obliges every BLOCKED 🔴 turn to halt and emit a `## Message`, the service spares a plan carrying `## Message` with a `SUCCESS` report, and `preserve_message_turns` admits communicating turns to the prune-exempt session scope. The corpus confirms it 1 for 1 — 1 red plan, 1 messaged — against 120 amber plans of which 3 message. The amber turn is the only reachable target today.
- Config removal is behaviour-neutral on its own: `get_setting` falls back to the live merged mapping for an undeclared key, and the shipped `config.yaml` carries `prune_failure_history: true`, so the service keeps reading the old value until its predicate goes. That is what lets the Interface commit stand alone.
- `_check_report_is_success` and `_check_file_contains` have no caller anywhere in `src` or `tests`. They are dead independently of this deletion and sit in the file being cleaned.
- Harness: `tests/harness/setup/pruning_scenarios.py` models paths, token counts, git status and scope only, so no scenario can express a plan status. There is no Harness deliverable to write.
- Guardrail for implementation: confirm that `turn_statuses` feeds nothing but the recovery-cleanup branch before deleting it. If it also feeds a sparing rule, stop and report rather than working around it.

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

## Edge Cases
- **Amber plan, successful report:** stays selected after a later green turn, because the heuristic that removed it no longer exists. This is the case the corpus measures.
- **Amber plan whose report failed validation:** still removed by validation pruning once a later non-validation turn succeeds. The two heuristics overlapped on such a turn and only the validation one keeps its behaviour, so the deletion must not also disable that branch.
- **Red plan:** unchanged. It is a communicating turn, spared by the message rule and pinned into the session scope, so the deletion does not make it newly prunable.
- **Stale config key:** an unknown nested key is dropped silently at config construction, so a user who set the key keeps a dead line in their `config.yaml` with no error and no warning. Anyone who set it to `false` did so to stop failures being pruned, which the new behaviour matches, so no migration note is required.
- **`_collect_turn_metadata` return shape:** losing the `statuses` key changes the mapping's shape. Every reader lives inside the service, so the shrink stays internal; assert the two survivors keep their keys and semantics.
- **Retention and budget untouched:** after the deletion a corpus census should still show validation, retention and budget holes. Only plan-status holes disappear, so a census that loses more than those indicates an over-deletion.

## Key Unknowns
None. Every remaining question is answerable by reading the service body, and the four members of the chain have already been read.

## Impact
1. `[PRUNE]` `ConfigSchema.AutoPruningConfig.prune_failure_history` and its `_SCHEMA_FIELDS` entry — the key stops being declared.
2. `[PRUNE]` `src/teddy_executor/resources/config/config.yaml` — the shipped `prune_failure_history` line and its trailing comment.
3. `[PRUNE]` `SessionPruningService` heuristic chain — the `prune_non_green` config read, the `turn_statuses` collection, `_update_metadata_from_plan`, `_check_plan_failed`, and the recovery-cleanup branch that writes `Pruned failure history after successful recovery`.
4. `[MIGRATE]` `SessionPruningService._collect_turn_metadata` and `_apply_pruning_heuristics` — drop the status collection from the returned mapping and the parameter that carries it, keeping `current_status` for the validation branch.
5. `[PRUNE]` `SessionPruningService._check_report_is_success` and `_check_file_contains` — dead before this slice, removed here because they live in the file being cleaned.
6. `[MIGRATE]` the affected test modules — `test_session_orchestrator_pruning.py` (retire `test_execute_prunes_failure_history_heuristic`), `test_session_pruning_service_refinement.py` (retire the recovery-cleanup cases), `test_session_pruning_status_anchoring.py`, `test_session_pruning_robustness.py`, `test_session_pruning_retention_window.py`, `test_session_primary_path_pruning.py`, `test_session_pruning_windows.py` (drop the dead config-double key and any reason-string assertion), `test_validation_failure_pruning_timing_integration.py` (drop the three isolating `False` entries), `test_yaml_config_adapter.py` (drop the assertion that reads the key from the bundled config), and `test_context_management_ui.py` (rewrite the two acceptance cases around the surviving behaviour).
7. `[MIGRATE]` documentation surfaces — the `IConfigService` key table, the heuristics list in `session_pruning_service.md`, and the census bullet in `context-payload-format.md`, which must keep its measurement while noting that only validation and budget removal remain live.

## Deliverables
- [ ] **Interface** - Remove `prune_failure_history` from `AutoPruningConfig`, its `_SCHEMA_FIELDS` entry, and the shipped `config.yaml` line with its comment; drop the key from the `IConfigService` table and delete the adapter test assertion that reads it. Behaviour is unchanged at this commit: the merged mapping still supplies `true`, so the service reads the same value through the fallback path.
- [ ] **Core** - Delete the heuristic chain and retire the unit and integration cases that pin it in one commit, so the suite stays green at every step: the recovery-cleanup branch, the `prune_non_green` read, `turn_statuses`, `_update_metadata_from_plan`, `_check_plan_failed`, and the `statuses` key plus `turn_statuses` parameter. Keep `current_status` threading for validation pruning. Update the heuristics list in `session_pruning_service.md` and the spec's census bullet in the same commit, so no document describes a mechanism the code no longer has.
- [ ] **Migration** - Drive the surviving behaviour through the outermost boundary: the two acceptance cases in `test_context_management_ui.py` become "an amber turn survives recovery" and "a validation-failed turn is still pruned", and every pruning config double across the suites loses the dead key.
- [ ] **Cleanup** - Remove `_check_report_is_success` and `_check_file_contains`, which have no caller in `src` or `tests`. If implementation finds a dynamic caller, drop this deliverable and record the finding rather than preserving dead code around it.

## Implementation Notes
Not yet started.

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
