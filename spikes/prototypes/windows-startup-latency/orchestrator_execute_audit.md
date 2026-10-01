# Audit: `orchestrator.execute` Call Sites & `project_context` Propagation (Slice 00-20 / Unknown 3)

**Method:** `git grep -n "\.execute(" -- src/` (turn 2) + full source reads of
`session_lifecycle_manager.py`, `session_orchestrator.py`, `session_planner.py`,
`session_replanner.py`, `cli_helpers.py`, `__main__.py` (turns 2-3).

## Call-site classification

| # | Site | Path type | `project_context` today | Gather analysis |
|---|------|-----------|------------------------|-----------------|
| 1 | `session_lifecycle_manager.py:62` (PENDING_PLAN branch) | session | Receives the parameter faithfully, but callers pass `None` (the session loop in `session_cli_handlers._orchestrate_session_loop` calls `orchestrator.resume(...)` with no `project_context`) | Re-gather at `session_orchestrator.py:264` when the plan pre-exists. This is the SINGLE gather for such turns (replanned turns executed on the next loop iteration; resumed interrupted turns). Not a double-gather by itself. |
| 2 | `session_lifecycle_manager.py:144` (`_handle_planning_and_execution`) | session (new turn via EMPTY state — reached from `teddy start` turn 01 AND from `teddy resume` on a COMPLETE_TURN → next turn) | Passes the parameter through (None today) | **DOUBLE-GATHER** — `generate_plan` gathers (planning_service.py:73) and writes `input.md`; then `orchestrator.execute` re-gathers at session_orchestrator.py:264 within the same resume call. **Fixed by the planned Wiring** (thread context `generate_plan` → `trigger_new_plan` → `_handle_planning_and_execution` → `execute`). |
| 3 | `session_orchestrator.py:307` (delegation to `ExecutionOrchestrator`) | both | Propagates `project_context` correctly | Not a gather site. |
| 4 | `__main__.py:459` (`teddy execute`) | manual | None | No gather — non-session (no `meta.yaml` next to plan) → `is_session=False` → the gather branch is skipped entirely. |
| 5 | `cli_helpers.py:202` (`execute_valid_plan`) | manual | None | No gather — same manual path, non-session. (Even if pointed at a session turn's plan.md, it would be a single gather, not a double.) |
| — | `action_dispatcher.py:84` | — | n/a | False positive: `action_handler.execute`, not an orchestrator. |

## Path-level conclusions

- **start path (EMPTY state):** double-gather today → fixed by planned parameter threading (planning and execution occur inside the same `resume` call, so the context can be passed as a parameter).
- **resume path (COMPLETE_TURN → next turn):** funnels through the same `_handle_planning_and_execution` → fixed by the same threading.
- **resume path (PENDING_PLAN):** single gather only — correct as-is.
- **replan path (validation failure):** `trigger_replan` → `trigger_replan_turn` → `generate_plan` (gather #1, context discarded). The replanned plan is executed on the **NEXT session-loop iteration** via the PENDING_PLAN branch with `project_context=None` → gather #2 at session_orchestrator.py:264. **The planned parameter threading CANNOT fix this path** because the context cannot cross the session-loop boundary as a parameter.
- **manual execute:** zero gathers — safe.

## Residual risk & recommendation

The planned Wiring delivers single-gather for the start and resume-next-turn paths. For replan turns (validation failures only — rare), two options:

- **(a) Persistence:** persist the `ProjectContext` produced during replan planning (e.g., to the turn directory) and reload it in the PENDING_PLAN branch. Full coverage, but adds a persistence contract across process/loop boundaries.
- **(b) Acceptance:** accept the residual single re-gather on validation-failure turns only (bounded, rare), and log it as follow-up debt.

**Recommendation:** (b) for this slice's scope — log (a) as `[DEBT]` in PROJECT.md — unless the user wants full coverage now.