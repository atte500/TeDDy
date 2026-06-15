# Bug: TUI Token Count Shows 0.0k

- **Status:** Resolved (Shadow Verified)
- **Milestone:** [Milestone 3: TUI & UX Enhancements](/docs/project/milestones/02-stability-and-polish.md)
- **Vertical Slice:** N/A (Trivial fix - 4 lines in `planning_service.py`)
- **Specs:** [Interactive Session Workflow](/docs/project/specs/interactive-session-workflow.md)

## Symptoms

**Expected:** The TUI (Textual Plan Reviewer) should display the token count for the current session (e.g., "1.2k" or "3.5k"), reflecting the total tokens consumed so far. The "• System" line in the Context Aggregate View should show the system prompt token count (e.g., "2.5k"), and the "Total Context" should include it.

**Actual:** The token count always shows "0.0k" regardless of session activity. The "• System" line reads "0.0k" and "Total Context" is missing all system prompt tokens from its sum.

**Minimal Reproduction Steps:**
1. Start a TUI session using `teddy execute` with a plan containing LLM actions.
2. Observe the token count display in the TUI's context panel.
3. Note that the "• System" line remains at "0.0k" and "Total Context" is undercounted.

## Context & Scope

### Regressing Delta
Not a regression — this is a **design gap** that has existed since the `PromptManager.fetch_system_prompt()` method was introduced. The `ProjectContext` DTO was designed with `system_prompt_tokens: int = 0` as a hardcoded default, but `PlanningService.generate_plan()` never updates it after the system prompt is resolved.

**The gap:**
1. `ContextService.get_context()` is called FIRST — hardcodes `system_prompt_tokens=0` (line 92 of `context_service.py`)
2. `PromptManager.fetch_system_prompt()` is called SECOND — now the system prompt text is available
3. The system prompt token count is **never propagated back** to the `ProjectContext` DTO

### Environmental Triggers
- All environments — this is a logical data-flow gap, not platform-dependent

### Ruled Out
- **Context item `token_count` per file:** Verified working correctly via `ContextService._get_path_to_tokens()` (parallelized via ThreadPoolExecutor)
- **LiteLLM adapter token counting:** `LiteLLMAdapter.get_text_token_count()` is fully functional (used for per-file counts)
- **TUI display logic:** `textual_plan_reviewer_helpers.py` correctly reads `app.project_context.system_prompt_tokens` — the data simply isn't there
- **LLM response parsing:** The `token_count` from `response.usage` is handled separately via `update_meta()`; not related to display
- **Session metadata (`meta.yaml`):** Turn cost and cumulative cost are correctly persisted; the TUI token display reads from `ProjectContext`, not `meta.yaml`

## Diagnostic Analysis

### Causal Model
```
PlanningService.generate_plan()
  │
  ├─ Step 1: get_context() ───────────────────────────────────┐
  │   Returns ProjectContext(system_prompt_tokens=0)           │
  │   (ContextService hardcodes this to 0 at line 92)          │
  │                                                            │
  ├─ Step 2: fetch_system_prompt()                             │
  │   Returns system prompt text string                        │
  │   (The token count COULD be computed here, but isn't)      │
  │                                                            │
  ├─ Step 3: Build messages list                               │
  │   messages = [                                             │
  │     {"role": "system", "content": system_prompt},          │
  │     {"role": "user", "content": context},                  │
  │   ]                                                        │
  │   (System prompt IS included in the LLM request,           │
  │    but its token count is never written to the DTO)        │
  │                                                            │
  └─ Step 4: TUI reads ProjectContext                          │
      app.project_context.system_prompt_tokens  → 0.0k        │
      (BUG: System prompt tokens always display as 0.0k)      │
```

**Root Cause:** `system_prompt_tokens` is a stale field on the `ProjectContext` DTO. It's initialized to `0` at construction time and never updated after the system prompt content becomes available.

### Discrepancies
- The `ProjectContext` DTO defines `system_prompt_tokens: int = 0` as a default, implying it will be populated by the caller. However, `ContextService.get_context()` always returns it as `0` because it doesn't have access to the system prompt. (Resolved: The fix propagates the token count in `PlanningService.generate_plan()` after `fetch_system_prompt()` returns.)

### Investigation History

1. **Initial grep analysis.** Found token display logic in `textual_plan_reviewer_helpers.py` (lines 59, 74, 146) and `system_prompt_tokens=0` hardcoded in `context_service.py:92`. Conclusion: The data is never populated in the DTO.

2. **Source file reading.** Traced the full data flow:
   - `ContextService.get_context()` creates `ProjectContext` with `system_prompt_tokens=0` (line 92)
   - `PlanningService.generate_plan()` calls `get_context()` first, then `fetch_system_prompt()` second
   - The TUI helpers read `app.project_context.system_prompt_tokens` — always 0
   Conclusion: The system prompt token count is computed too late in the flow and never backfilled.

3. **MRE creation and execution.** Built a self-contained MRE that confirmed:
   - `ContextService.get_context()` always returns `system_prompt_tokens=0` (CONFIRMED)
   - TUI display shows "0.0k" for system tokens (CONFIRMED)
   - `PlanningService.generate_plan()` calls `get_context()` before `fetch_system_prompt()` (CONFIRMED flow gap)
   Conclusion: Root cause is a data-flow gap in `PlanningService.generate_plan()`.

4. **Shadow file fix verification.** Created `shadow_planning_service.py` with a 4-line fix that computes `system_prompt_tokens` after `fetch_system_prompt()` and updates the DTO. Test confirmed:
   - `system_prompt_tokens` BEFORE fix: 0
   - `system_prompt_tokens` AFTER fix: 2000 (correctly propagated)
   - `get_text_token_count` called with correct system prompt text and model (VERIFIED)
   Conclusion: Fix works via shadow file methodology.

## Solution

### Root Cause
A data-flow gap in `PlanningService.generate_plan()`: the `ProjectContext.system_prompt_tokens` field is initialized to `0` by `ContextService.get_context()` and is never updated after the system prompt is resolved via `PromptManager.fetch_system_prompt()`.

### The Fix (4 lines in `planning_service.py`)
After `fetch_system_prompt()` returns, compute the token count and update the DTO:

```python
system_prompt = self._prompt_manager.fetch_system_prompt(agent_name, turn_path)

# === FIX: Propagate system prompt tokens to the ProjectContext DTO ===
model = str(
    meta.get("model")
    or self._config_service.get_setting("llm.model")
    or "gpt-4o"
)
try:
    system_token_count = self._llm_client.get_text_token_count(
        system_prompt, model=model
    )
except Exception:
    system_token_count = 0
object.__setattr__(context, "system_prompt_tokens", system_token_count)
```

**Why `object.__setattr__`?** Because `ProjectContext` is a frozen `dataclass` (immutable by convention, though not decorated with `frozen=True`). Using `object.__setattr__` avoids needing to refactor the entire DTO to a builder pattern for this single field.

### Preventative Measures
To prevent this entire class of "data-flow gap" bugs globally:

1. **Checklist for DTO population completeness:** When a DTO field is initialized to a constant default (like `=0`), verify it's actually populated by at least one code path before the DTO reaches consumers.

2. **Secondary fix (non-TUI path):** `session_orchestrator.py` line 143 also hardcodes `system_prompt_tokens=0`. When refactoring, this should also be fixed to accept the token count from the planning service output.

3. **Architectural improvement (future):** Consider making `PlanningService` responsible for computing `system_prompt_tokens` before constructing the `ProjectContext` DTO. This could be achieved by:
   - Adding a `system_prompt` parameter to `ContextService.get_context()` so it can compute the token count at construction time
   - OR making `ProjectContext` mutable for fields that are filled asynchronously (builder pattern)
