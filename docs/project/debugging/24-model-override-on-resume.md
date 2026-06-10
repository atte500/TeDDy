# Bug: Model Override Not Applied on First Turn of `teddy resume`

- **Status:** Resolved
- **Milestone:** [02-stability-and-polish](/docs/project/milestones/02-stability-and-polish.md)
- **Vertical Slice:** N/A (trivial fix)
- **Specs:** N/A

## Symptoms

**Expected:** When resuming a session via `teddy resume -m "override-model"`, the first turn should use the provided model override (same behaviour as `teddy start -m "override-model"`).

**Actual:** The first turn of a resumed session uses the original model stored in the session metadata, ignoring the `-m` flag. In practice, the telemetry display shows the stale `actual_model` from a previous completion instead of the current model (override or default).

**Reproduction Steps:**
1. Start a session without model override (or with a known model). Let the first turn complete (LLM call stores `actual_model` in meta.yaml).
2. Resume the session with a different model via `-m` flag.
3. Observe that the `• Model:` telemetry line still shows the old `actual_model` from step 1, not the override.

## Context & Scope

### Regressing Delta
The root cause is a display priority issue in the resume telemetry pipeline. When `teddy resume` calls `_sync_and_display_session_meta`, it writes the override to `meta["model"]`, but the existing `meta["actual_model"]` (stale from a previous completion) takes precedence in two display locations:

1. `_echo_config_success` (line 164): `if actual_model: resolved_model = actual_model`
2. `_display_telemetry` (line 193): `meta.get("actual_model") or meta.get("model")`

The override in `meta["model"]` is correctly used for the actual LLM call (confirmed by MRE), but the display shows the stale `actual_model`.

### Environmental Triggers
- Triggered when resuming a session that has at least one completed turn (storing `actual_model` in meta.yaml).
- Does not affect sessions with no prior completions (EMPTY state).

### Ruled Out
- The model override does propagate correctly to the new turn's meta.yaml via `_persist_next_meta`. (Confirmed by MRE: `spikes/debug/24-model-override-mre.py` PASS.)
- The LLM completion uses the overridden model correctly (confirmed by code analysis).
- The PENDING_PLAN branch is a separate gap where the override cannot affect an existing plan.

## Diagnostic Analysis

### Causal Model
The resume flow for a COMPLETE_TURN session:
1. `handle_resume_session` calls `_sync_and_display_session_meta(container, session_name, model=override)`.
2. Inside `_sync_and_display_session_meta`: loads meta from latest turn, writes `model=override` to meta dict, saves. BUT `actual_model` from the previous completion is still in the meta dict.
3. The function then calls `_echo_config_success(container, model=override, actual_model=meta.get("actual_model"))` → since `actual_model` is present, it is displayed instead of the override.
4. After `transition_to_next_turn` → `_persist_next_meta` carries both `model` and `actual_model` to the new turn's meta.
5. `generate_plan` → `_display_telemetry` reads `meta.get("actual_model") or meta.get("model")` → the stale `actual_model` wins.

### Discrepancies
- `_sync_and_display_session_meta` does not clear `actual_model` on resume, causing display to prefer a stale value. (Resolved: fix clears `actual_model` unconditionally on resume.)
- PENDING_PLAN resume branch executes stale plan without re-generating with override. (Separate issue, documented as debt.)

### Investigation History
1. Traced resume pipeline from CLI handler → meta.yaml sync → turn transition → planning → LLM call. Confirmed override is written to source meta.yaml.
2. Built MRE (`spikes/debug/24-model-override-mre.py`) simulating `_persist_next_meta` logic. MRE PASS: override propagates to new turn's meta.yaml.
3. Identified display priority (`actual_model` > `model`) in `_echo_config_success` and `_display_telemetry` as the root cause of the visual bug.
4. User confirmed fix: delete `actual_model` on every resume (not just when override is provided), so display falls back to current model.
5. Systemic audit: searched for other `actual_model` > `model` priority patterns – only the two identified locations exist.

## Solution

### Root Cause
When resuming a session, `_sync_and_display_session_meta` writes the current model (override or config default) to `meta["model"]` but leaves the stale `meta["actual_model"]` intact. Both display points (`_echo_config_success` and `_display_telemetry`) prioritize `actual_model` over `model`, causing the display to show the previous turn's actual serving model instead of the current model.

### Fix
In `_sync_and_display_session_meta`, after loading the meta dict and before saving, **unconditionally delete the `actual_model` key**:
```python
meta.pop("actual_model", None)
```
This ensures the display falls through to `meta["model"]` (which reflects the current override or config default). After the first LLM completion, `PromptManager.update_meta` repopulates `actual_model` from `response.model`.

### Preventative Measures
- Any future display/telemetry logic should treat `actual_model` as a transient value that must be refreshed after each completion. It should never be displayed from a prior turn's state.
- Consider a general rule: metadata that reflects execution state (like `actual_model`, `finish_reason`) should be cleared on session transitions (resume) to prevent stale display.
