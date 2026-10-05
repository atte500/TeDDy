# Task: Single-Folder Sessions — Turn Numbering Past 99 & Context Read-Cap Exclusion

## Business Goal
Let a single session run past turn 99 without migrating into a continuation folder or silently truncating its session-history files, so `input.md` stays accurate and complete for long sessions.

## Context

### Problem

Today a session **migrates** at turn 99. `SessionService._resolve_next_turn_path` ([session_service.py](/src/teddy_executor/core/services/session_service.py)) detects `cur_dir.name == "99"` and returns turn `"01"` inside a NEW cloned continuation session root (`<name>-2`), flagged `is_migration=True`. `transition_to_next_turn` then claims that root, clones `session.context` + the active prompt via `_clone_session_artifacts`, and restarts numbering at `01`.

This creates a **namespace collision**: the previous session's `01` and the new session's `01` both render as `### Turn 1` under `## Session History`, and the `**Current Turn:**` header resets to `01` with no continuation signal. Migration exists **only** to preserve 2-digit padding (Milestone 2) — not a technical requirement.

Separately, files embedded into `input.md` are being **silently truncated**. `LocalFileSystemAdapter.read_files_in_vault` (the context-assembly loader, [local_file_system_adapter.py](/src/teddy_executor/adapters/outbound/local_file_system_adapter.py)) calls `self.read_file`, which applies `truncate_lines(..., max_lines=self.max_read_lines)` where `read.max_lines: 1000` ([config.yaml](/src/teddy_executor/resources/config/config.yaml)). So session-history files (`plan.md`, `report.md`, `initial_request.md`) and workspace files are cut off at 1000 lines in the AI's worldview. The config comment states the setting only "Caps READ action output", so this is a leak of the cap into context assembly rather than an intended exclusion.

### Approved Decisions

1. **Kill migration → ONE folder per session.** A session never spawns continuation roots; turns simply increment (`... 99, 100, 101`).
2. **Fix the one integer-sort site.** `SessionRepository.get_latest_turn` uses lexicographic `sorted(turns)[-1]`, which wrongly picks `99` over `100`.
3. **Keep `:02d` padding.** `f"{n:02d}"` is a *minimum* width, so `100` renders as `"100"` with no format change. Keeping it makes migration-removal a pure deletion and lets every other `:02d` site (e.g. `session_lifecycle_manager.py`) keep working for 3-digit turns. Fully retro-compatible; no folder renaming.
4. **Exclude context-embedded files from the READ cap.** The cap is a READ-*action* concern; context assembly must read verbatim.

### Supersedes

This removes the "Session Migration" requirement recorded under **Milestone 2 (Stability & Infrastructure)**. That requirement has been retired across the living planning docs as part of this change — `docs/project/PROJECT.md` (Milestone 2), `docs/project/milestones/02-stability-and-polish.md`, `docs/project/specs/interactive-session-workflow.md` (§6 Turn Numbering), `docs/architecture/core/services/session_service.md` (Migration Algorithm section), and `docs/architecture/core/ports/outbound/file_system_manager.md` (the `turn-100 migration` intended-use note). (Those doc edits are the Pathfinder's Documentation-phase alignment; this Task Brief remains scoped to the Developer's CODE changes only and does NOT itself touch `PROJECT.md`.)

### Out of Scope

- The `yolo_guardrails.max_turns: 99` safety limit in `config.yaml` is a **separate** mechanism (it terminates `--yolo` runs at 99 turns). Do NOT change it here.
- No data migration or folder renaming. Existing `<name>-2` continuation folders stay on disk untouched and remain independently resumable.

## Implementation Steps

### Step 1: Remove session migration from turn resolution

- **File:** [src/teddy_executor/core/services/session_service.py](/src/teddy_executor/core/services/session_service.py)
- **Change:** Eliminate the migration concept entirely (single logical change across three members):
    - In `_resolve_next_turn_path`, delete the `if cur_dir.name == "99":` branch that returns `"01"` + a continuation root + `True`. Always compute `next_id = f"{int(cur_dir.name) + 1:02d}"` and resolve the next directory as the SAME session (`cur_dir.parent`). Keep the `:02d` format (minimum width renders `100`, `101`, … correctly). Drop the third (migration) element from the return value and update the type hint to `tuple[str, Path]`.
    - In `transition_to_next_turn` (the sole caller — verify with `git grep "_resolve_next_turn_path"`), remove both `if is_migration:` blocks (the `_claim_session_root` claim and the `_clone_session_artifacts` call) and the `is_migration` unpacking.
    - Delete the now-dead `_clone_session_artifacts` method.
- **Do NOT delete** `_calculate_continuation_name` or `_claim_session_root` — they are still used by `create_session` for the session-*name* collision guard (Slice 00-19). Only the migration branch is removed.

### Step 2: Fix `get_latest_turn` to sort turns numerically

- **File:** [src/teddy_executor/core/services/session_repository.py](/src/teddy_executor/core/services/session_repository.py)
- **Change:** In `get_latest_turn`, replace the lexicographic `latest_turn_id = sorted(turns)[-1]` with a numeric sort: `latest_turn_id = max(turns, key=int)` (or `sorted(turns, key=int)[-1]`). This is mandatory so that turn `100` resolves after `99`. `turns` is already filtered to numeric directory names (`item.isdigit()`).

### Step 3: Read context files verbatim (bypass the READ cap)

- **File:** [src/teddy_executor/adapters/outbound/local_file_system_adapter.py](/src/teddy_executor/adapters/outbound/local_file_system_adapter.py)
- **Change:** In `read_files_in_vault`, replace the `self.read_file(path)` call with `self.read_raw_file(path)`. `read_raw_file` reads full, untruncated content and raises `FileNotFoundError` identically, so the existing `except FileNotFoundError: contents[path] = None` handling stays intact. This affects ONLY context assembly (the sole caller is `context_service.py:65`), leaving the READ *action* cap in `read_file` unchanged and correct.
- Also update the docstrings on `read_files_in_vault` (adapter) and the `IFileSystemManager.read_files_in_vault` contract ([file_system_manager.py](/src/teddy_executor/core/ports/outbound/file_system_manager.py)) to state that it returns **full** content (no truncation), in contrast to `read_file` which honours `read.max_lines`.

### Step 4: Align URL context content with the cap decision (investigate, then act)

- **File:** [src/teddy_executor/adapters/outbound/web_scraper_adapter.py](/src/teddy_executor/adapters/outbound/web_scraper_adapter.py)
- **Change:** Locate the method that truncates markdown via `read.max_lines` (~line 290) and determine whether it is invoked on the **context-assembly** path (`IWebScraper.get_content`, called from `context_service._fetch_and_cache_url`). If it IS, context-embedded URLs are also silently truncated and should be returned in full for context assembly (e.g. add a non-truncating variant or gate the truncation to the READ-action call path only). If it is NOT on the context path, make no change and record the finding in the commit message. Prefer the smallest change that restores parity with Step 3.

### Step 5: Remove stale "migration" docstrings/comments

- **Files:** [src/teddy_executor/core/services/session_lifecycle_manager.py](/src/teddy_executor/core/services/session_lifecycle_manager.py) and [src/teddy_executor/core/ports/inbound/run_plan_use_case.py](/src/teddy_executor/core/ports/inbound/run_plan_use_case.py)
- **Change:** Update the docstrings/comments that describe a "migration (when the session transitions to a continuation name…)" so they reflect the single-folder model (a session never spawns continuation roots). Search for `migrat`/`continuation` across `src/teddy_executor` and fix any remaining prose references introduced by this removal.

### Step 6: Update and add tests

- **Files:** [tests/suites/unit/core/services/test_session_service_transition.py](/tests/suites/unit/core/services/test_session_service_transition.py), [tests/suites/unit/core/services/test_session_repository.py](/tests/suites/unit/core/services/test_session_repository.py), [tests/suites/unit/adapters/outbound/test_file_system_adapter_capping.py](/tests/suites/unit/adapters/outbound/test_file_system_adapter_capping.py) (and any sibling migration-specific tests surfaced by `git grep -nE "is_migration|_clone_session_artifacts|continuation|migrat" tests/`)
- **Change:**
    - Remove/rewrite tests that assert migration behaviour (a `-2` continuation root created at turn 99).
    - Add a unit test asserting `_resolve_next_turn_path` at `"99"` returns `("100", <same session dir>)` — no new session root, no migration flag.
    - Add a unit test asserting `get_latest_turn` returns the `100` directory when `01`–`100` exist.
    - Add a test asserting `LocalFileSystemAdapter.read_files_in_vault` returns the FULL content of a file whose line count exceeds `read.max_lines` (no truncation).
    - Ensure no test creates stray `.teddy/` artifacts (the suite's pollution guard must stay green).

## Verification

1. `uv run pytest tests/suites/unit/core/services/test_session_service_transition.py tests/suites/unit/core/services/test_session_service.py tests/suites/unit/core/services/test_session_repository.py tests/suites/unit/adapters/outbound/test_file_system_adapter_capping.py tests/suites/unit/adapters/outbound/test_file_system_adapter_contract.py -q` passes.
2. `uv run pytest -q` (full suite) passes — no regressions, no filesystem pollution.
3. `git grep -n "_clone_session_artifacts" src/` returns NOTHING (method fully removed).
4. `git grep -nE "is_migration" src/` returns NOTHING.
5. `git grep -n "_calculate_continuation_name\|_claim_session_root" src/` still shows them present and used by `create_session` (name-collision guard intact).
6. Manual end-to-end (or a targeted transition test): driving a session to turn `100` creates `.teddy/sessions/<name>/100/` in the SAME folder, and NO `<name>-2` sibling is created.
7. Manual: a `report.md` longer than `read.max_lines` (1000 lines) appears VERBATIM in the next turn's `input.md` (`## Session History`) — not truncated.
8. Retro-compatibility: an existing `.teddy/sessions/<name>-2/` folder still resumes correctly and its turns still sort/render.
