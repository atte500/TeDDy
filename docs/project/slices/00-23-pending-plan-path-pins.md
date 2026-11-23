# Slice: Pin Pending-Plan Path Doubles for the Marker Read
- **Status:** In Progress
- **Milestone:** Ad-hoc (no milestone)
- **Depends On:** [00-22-execution-started-marker.md](/docs/project/slices/00-22-execution-started-marker.md)
- **Specs:** N/A
- **Prototype:** N/A
- **Component Docs:** N/A (test-only slice)
- **Scope Slug:** `pending-plan-pins`

## Goal
Make the pending-plan unit suites answer `path_exists` by path so their never-dispatched turns read "no marker" once the resume gate lands. This is behavior-preserving today because production does not read the marker yet.

## Context
- `tests/suites/unit/core/services/test_session_lifecycle_pending_plan_non_communication_resume.py:127-134` sets `path_exists.return_value = present`.
- `tests/suites/unit/core/services/test_session_lifecycle_pending_plan_blank_message.py` never configures `path_exists`, so it defaults to a truthy Mock.
- `tests/suites/unit/core/services/test_session_lifecycle_pending_plan_communication_resume.py` already keys `path_exists` to `meta.yaml`.
- `EXECUTION_STARTED_MARKER` from slice 00-22 is the single source for the marker filename.
- Cross-platform rule: a path-matching `side_effect` compares through `mocking.to_posix_path`.

## Scenarios
> As the developer adding the resume gate, I want the pending-plan suites to report the marker absent, so their never-dispatched turns keep today's in-place completion.

```gherkin
Given the non-communication and blank-message suites arrange a pending action turn
When the manager checks whether execution.started exists
Then the double reports False for execution.started
And preserves its existing answers for report.md and meta.yaml
```

## Edge Cases
- **Report presence toggle**: If a test drives `report.md` present or absent, then the marker still reads False while `report.md` keeps the test's chosen presence.
- **Other paths**: If a path is not the marker, then the double keeps its prior behavior so existing assertions hold.
- **Windows**: If a path is matched, then both sides normalize through `to_posix_path` so slash differences cannot flip the answer.

## Key Unknowns
None. Both suites' `path_exists` configuration is known by inspection.

## Impact
1. `[NEW]` shared harness helper in `tests/harness/setup/mocking.py` — a `path_exists` side-effect factory that reports the marker absent and forwards a default answer for every other path.
2. `[MIGRATE]` non-communication suite — route `_arrange_resumed_turn_report` and the base arrange through the helper.
3. `[MIGRATE]` blank-message suite — set the helper on the `manager` fixture.
4. `[PRUNE]` none.

## Deliverables
- [x] **Harness** - Add the shared `path_exists` side-effect factory (marker absent) to `tests/harness/setup/mocking.py` and unit-test the factory in isolation.
- [ ] **Migration** - Route both pending-plan suites through the factory, preserving each test's report-presence toggle, then confirm the full suite stays green.

## Implementation Notes
- **Harness (marker-absent `path_exists` factory):** `path_exists_marker_absent(default=True)` lives in `tests/harness/setup/mocking.py` beside `register_mock`. It single-sources the marker filename from `EXECUTION_STARTED_MARKER` (imported from the port), normalizes the incoming path through `to_posix_path`, takes the basename, and returns `False` when that basename is the marker while forwarding `default` for every other path. Red was an `ImportError: cannot import name 'path_exists_marker_absent'` observed at collection, proving the new cases bind a real single-sourced helper rather than a locally re-declared lambda. Green produced `12 passed` (four new factory cases plus the eight pre-existing normalizer/consumer cases) and `make test` stayed green at `2321 passed, 5 skipped`, because the factory has no production caller yet. The four cases in `TestPathExistsMarkerAbsent` pin: marker absent while other paths forward `present`; marker absent while other paths forward `absent`; a Windows-separator marker path matching after normalization; and the bare marker filename. A refactor pass tightened the docstring so it claims only the incoming-path normalization the code performs, since only the argument side is normalized and the marker side is a separator-free literal.

## Verification
1. **Focused suites green:**
   Run `make test` and confirm the four pending-plan suites and the new harness factory test pass.
2. **Behavior preserved:**
   Confirm the non-communication suite's report-present and report-absent cases still assert their original outcomes, now with `execution.started` reading False.
