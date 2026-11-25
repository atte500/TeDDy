# Bug: Deleted Composed Prompt Is Not Recomposed and Re-Saved
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** [Interactive Session Workflow](../specs/interactive-session-workflow.md)

## Symptoms
Expected: the session-root file holds the exact composed system prompt sent to the model (Option A: agent content + `---` separator + MRP). If the user deletes that file from the session folder, the next system-prompt read should recompose it from `.teddy/prompts/` AND write it back to the session root, so later turns reuse the persisted value verbatim.

Actual: `PromptManager.fetch_system_prompt` does recompose the prompt in memory when the session-root file is missing (so the model still receives a correct prompt), but it never writes the recomposed value back. The session root stays empty and every subsequent turn re-runs the composition.

Minimal reproduction:
1. Create a session; the composed prompt is written to `.teddy/sessions/<name>/<agent>.<ext>`.
2. Delete `<agent>.<ext>` from the session root.
3. Read the system prompt for the next turn (or resume the session).
4. Observe: the prompt is recomposed in memory; the session-root file is still absent.

## Context & Scope
### Regressing Delta
- Commit `a4054cd8` (`refactor(session-behaviour): persist and reuse the composed system prompt`) introduced Option A: `SessionService.create_session` / `set_session_agent` compose and persist the prompt at the session root, and `PromptManager.fetch_system_prompt` returns it verbatim when present. The same commit added the lazy-compose fallback for a "legacy session or manually deleted file" but gave that fallback no write-back.
- File: `src/teddy_executor/core/services/prompt_manager.py`, `fetch_system_prompt` lines 151–169 (fallback at 161–169).

### Environmental Triggers
- Any OS/runtime. Triggered whenever the session-root composed prompt file is absent while the canonical `.teddy/prompts/<agent>.<ext>` source still resolves (deleted composed prompt, or a pre-Option-A legacy session).

### Ruled Out
- Prompt composition correctness: the fallback already assembles the exact `agent content + --- + MRP` value in memory.
- `.teddy/prompts/` resolution: `_find_prompt_file` is extension-agnostic and case-insensitive and resolves the source correctly.
- MRP loading: `_load_mrp_base_prompt` resolves the injected/bundled resource and fails fast when missing.
- Session creation / agent-switch persistence: both `SessionService` write sites persist the composed prompt correctly.

## Diagnostic Analysis
### Causal Model
- `SessionService.create_session` / `set_session_agent` call `PromptManager.fetch_system_prompt` while the session root is empty, forcing the compose path, then write the result to the session root. That establishes the invariant "the session-root file IS the composed prompt".
- `PromptManager.fetch_system_prompt(agent_name, turn_path)`:
  1. Searches `turn_path.parent` (the session root) for `<agent>.<ext>`. If found, returns it verbatim.
  2. Otherwise (deleted/legacy), resolves `<agent>.<ext>` from `turn_path.parent.parent.parent.parent/.teddy/prompts/`, reads it, assembles `content + "\n\n---\n\n" + MRP`, and returns the string.
- The fallback contains no `write_file` call, so the session-root invariant is never re-established after deletion. Each later turn repeats step 2.

### Discrepancies
- [x] Session-root prompt read returns the persisted composed prompt verbatim (Resolved: Option A verbatim-read path confirmed by `test_fetch_system_prompt_returns_persisted_composed_prompt_verbatim`).
- [x] Session creation / agent switch persist the composed prompt (Resolved: confirmed in `SessionService` and its tests).
- [x] A deleted session-root prompt is recomposed AND re-saved (Resolved: the lazy-compose fallback now re-persists the composed value at the session root under the source basename; proven in the sandbox replica and applied directly to `prompt_manager.py`).

### Investigation History
1. Located the composition and persistence seams via `git grep` for `composed`/`prompt.md`: `PromptManager._assemble_composed_prompt` composes; `SessionService` persists at the session root. Observed the read path returns a session-root file verbatim and otherwise lazy-composes.
2. Read `PromptManager`, its outbound port, and the component design doc. Observed the fallback returns the assembled string without persisting; `_resolve_agent_prompt_content` has a single caller (`fetch_system_prompt`).
3. Inspected `SessionService.create_session`/`set_session_agent`, `_resolve_agent_prompt`, `LocalFileSystemAdapter.write_file`, and the PromptManager tests. Observed both write sites derive the session-root filename from the `.teddy/prompts/` source basename and call `write_file`; `write_file` overwrites and writes utf-8.
4. Built the MRE at `spikes/debug/deleted-composed-prompt/01-recompose-persist-mre.py` (real `PromptManager` + real `LocalFileSystemAdapter` on a temp workspace) and ran it against production code. Observed `recomposed content correct: True`, `persisted at session root: False`, exit 1 — the bug is reproduced live: recomposition succeeds in memory, but nothing is written back and the session root stays empty.
5. Created the sandbox replica at `spikes/debug/deleted-composed-prompt/replica_prompt_manager.py` carrying the proposed write-back and repointed the MRE at it. Observed `recomposed content correct: True`, `persisted at session root: True`, exit 0 — the write-back restores the Option A invariant after deletion, proven without touching `src/`.
6. Applied the proven write-back directly to `src/teddy_executor/core/services/prompt_manager.py`: `_resolve_agent_prompt_content` now returns `(content, source_basename)` and `fetch_system_prompt` re-persists the composed value on the fallback. Added `test_fetch_system_prompt_repersists_deleted_session_prompt`; the full suite ran green (2534 passed, 5 skipped).
7. Repointed the preserved MRE back at the production `PromptManager` (the replica stays as the frozen pre-fix proof record) and reran it against the real filesystem adapter: `recomposed content correct: True`, `persisted at session root: True`, exit 0 — the shipped change heals the session root outside the test harness.

## Solution
### Root Cause
The Option A invariant "the session-root prompt file IS the composed system prompt" is established by `SessionService` at creation / agent switch, but is never re-established after the file is deleted. `PromptManager.fetch_system_prompt` only reads: when the session-root file is missing it composes the correct prompt in memory and returns it, but discards the result instead of writing it back. The session root therefore stays empty and every later turn re-composes. The fix re-persists the composed value inside that lazy-compose fallback, under the same source basename `SessionService` uses, so the invariant heals idempotently.

Verified in the sandbox replica (`spikes/debug/deleted-composed-prompt/replica_prompt_manager.py`) and then applied directly to `src/teddy_executor/core/services/prompt_manager.py` with a regression test.

### Affected Components
- `PromptManager.fetch_system_prompt` (`src/teddy_executor/core/services/prompt_manager.py`): now re-persists the composed prompt at the session root on the lazy-compose fallback; read-only when the file already exists.
- `PromptManager._resolve_agent_prompt_content`: now returns `(content, source_basename)` so the fallback can write under the exact session-root name `SessionService` uses. Single caller (`fetch_system_prompt`), so no migration.
- Upstream callers of `fetch_system_prompt`: `SessionService.create_session` / `set_session_agent` (their own write repeats the same bytes, so the fallback write is idempotent), `PlanningService`, `SessionOrchestrator` (both read during a turn and now heal a deleted file in place).
