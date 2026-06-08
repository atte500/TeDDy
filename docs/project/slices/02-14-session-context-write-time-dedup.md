# Slice: Session Context Write-Time Dedup
- **Status:** Completed
- **Type:** Refactor
- **Milestone:** [Milestone 02](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [Stability & Bugfixes](/docs/project/specs/stability-and-bugfixes.md)
- **Component Docs:** [SessionService](/docs/architecture/core/services/session_service.md)
- **Prototype:** [TBD]

## Business Goal
Add path deduplication in `SessionService._prepare_session_context()` before writing to `session.context`. Currently, `init.context` lines merged with `additional_context` can contain duplicate paths that are written to disk. The merged list must be deduplicated so that `session.context` never contains duplicate paths at creation time. Read-time dedup via `read_context_file` already handles the `session.context` → `resolve_context_paths` pipeline, but write-time dedup is a defensive best practice.

## Scenarios

> As a user, I want to start a session with `teddy start -c path_a,path_b` where `init.context` already contains `path_a`, so that `session.context` contains each path only once.

```gherkin
Given a project with `.teddy/init.context` containing "path_a" and "path_b"
When I run `teddy start -n test-session -c path_a,path_c`
Then the generated `session.context` contains exactly the entries:
  | path_a |
  | path_b |
  | path_c |
And each path appears only once
```

> As a user, I want an `init.context` that contains duplicates across comments and actual entries, so that `session.context` contains each entry only once after dedup.

```gherkin
Given an `init.context` file with content:
  # header comment
  path_a
  path_b
  path_a
When the session is created
Then `session.context` contains "path_a" exactly once
```

> As a user, I want the `initial_request.md` path to be deduplicated if it is already listed in `init.context` or `additional_context`, so that `session.context` has no duplicates.

```gherkin
Given `init.context` contains "initial_request.md"
And an initial request message is provided
When the session is created
Then `session.context` contains "initial_request.md" exactly once
```

## Edge Cases
- **Empty init.context**: If `init.context` is empty, `clean_lines` is an empty list; only `additional_context` are added, and the `initial_request.md` path is appended. No duplicates possible.
- **Comments only**: Comments are stripped, resulting in an empty list. Works the same as empty file.
- **Duplicate initial_request path in additional_context**: The `initial_request.md` path should be deduplicated even if the user explicitly passed it via `-c`. Currently the `initial_request` path is appended after dedup; needs to be added *before* dedup.
- **No additional_context**: Duplicates within `init.context` itself are deduplicated.

## Deliverables

- [x] **Logic** - Add order-preserving deduplication to `_prepare_session_context()`:
  1. Move the `initial_request` path addition *before* the dedup step so it's also deduplicated.
  2. Use a `seen = set()` and build an ordered list (`deduped = []`) by iterating `clean_lines` after merging `additional_context`.
  3. Add `initial_request.md` path to `seen`/`deduped` if not already present.
  4. Join with newline.
  - **Bundled Test**: Unit test verifying dedup behavior (multiple duplicate scenarios, order preservation, initial_request dedup).
- [x] **Harness** - Update any existing test fixtures that depend on the exact output of `session.context` (if any). Verify all related tests still pass.

## Implementation Notes
- **Logic Deliverable (Completed 2026-06-08):**
  - Restructured `_prepare_session_context` to add `initial_request.md` path to `clean_lines` **before** deduplication, rather than appending via string concatenation after joining. This ensures the `initial_request` path is also deduplicated.
  - Implemented order-preserving dedup using a `seen` set + ordered list pattern over `clean_lines` after merging `additional_context` and `initial_request` path.
  - **POSIXPathMock Fix**: Discovered that `to_root_relative()` returns a `POSIXPathMock` object (not a `str`) in some test environments. The old code implicitly converted via f-string (`clean_context += f"\n{rel_path}"`), but the new `join()` requires explicit `str()` wrapping. Added `str()` wrapping to `rel_path` before appending.
  - **Test Coverage**: Added `test_create_session_deduplicates_context_paths` to verify dedup behavior (init.context duplicates, overlapping additional_context, order preservation). Added `test_apply_execution_effects_skips_original_actions_when_action_logs_present` as regression coverage for Bug #16. All 832 tests pass (full suite).
  - **Debt (Minor)** : The dedup pattern is only 4 lines within `_prepare_session_context`. Extracting into a shared utility is not warranted at this point unless similar patterns arise elsewhere.
- **Harness Deliverable (Pre-verified):** The full test suite (832 tests) passed after the Logic change, confirming no existing test fixtures depend on the exact `session.context` output in a breaking way. The Harness deliverable is already satisfied.

## Implementation Plan
The change is localized to `_prepare_session_context` in `session_service.py`. No new interfaces, no wiring changes, no migration steps. The extraction of `initial_request` path addition is necessary so that dedup covers it. The pattern:
```python
def _prepare_session_context(self, session_root, options):
    # ... read init.context, strip comments -> clean_lines
    # Merge additional_context
    for path in options.additional_context:
        if path and path not in clean_lines:
            clean_lines.append(path)
    # Seed initial request (must happen BEFORE dedup)
    if options.initial_request:
        req_path = ...
        clean_lines.append(rel_path)
    # Deduplicate preserving order
    seen = set()
    deduped = []
    for line in clean_lines:
        if line not in seen:
            seen.add(line)
            deduped.append(line)
    clean_context = "\n".join(deduped)
    return clean_context
```
Note: The current code appends `initial_request` path *after* joining, which makes it impossible to dedup. This is the critical change.
