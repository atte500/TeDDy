# Slice: Pipeline Mode Defaults to the Assistant Agent
- **Status:** In Progress
- **Milestone:** N/A (ad-hoc)
- **Specs:** N/A
- **Prototype:** N/A
- **Component Docs:** [cli.md](/docs/architecture/adapters/inbound/cli.md)
- **Scope Slug:** `pipeline-default-agent`

## Business Goal

Make `teddy start --pipeline` (`-p`) runs default to the action-first `assistant` agent so automated / CI invocations begin executing actions immediately instead of opening with Pathfinder's discovery-and-alignment loop, while every other run keeps the `pathfinder` default. An explicit `-a` always wins. Source: [task brief](/docs/project/tasks/02-pipeline-default-agent.md).

## Scenarios

> As a TeDDy operator, I want pipeline runs to default to the assistant agent so automated runs execute actions immediately instead of opening with discovery.

```gherkin
Given a project configured with an LLM API key
When the user runs `teddy start -p -m "list the repo tree"`
Then the session resolves to the `assistant` agent
And the assembled system prompt begins `Agent Name: Assistant`
```

```gherkin
Given a project configured with an LLM API key
When the user runs `teddy start -m "survey the backlog"` (no `-p`)
Then the session resolves to the `pathfinder` agent
And the assembled system prompt begins `Agent Name: Pathfinder`
```

## Edge Cases

- **Explicit `-a` wins**: If the user passes `-a architect` (with or without `-p`), then the effective agent is `architect`, because an explicit flag overrides both defaults.
- **`resume` untouched**: If `teddy resume -p` runs, then the existing session's agent is left unchanged, because `resume`'s `-a` means "switch persona" and is deliberately out of scope.
- **Config-independent**: If no config is present, then resolution never consults `IConfigService`, because it is a pure function of the flag value and the pipeline boolean.
- **Help text accuracy**: If `teddy start --help` runs, then the `--agent` help text documents the pipeline-aware default ("Defaults to 'pathfinder' ('assistant' in pipeline mode).").
- **No regression on other commands**: If `execute` / `context` / `init` run, then they are unaffected, because only the `start` command's default changes.

## Key Unknowns

- [x] [Technical] The `start` command's `agent` option is a hard-coded `str` default `"pathfinder"` at `src/teddy_executor/__main__.py:168`; no `_resolve_agent` exists (greenfield).
- [x] [Technical] The resolution-helper pattern already exists (`_resolve_yolo` line 55, `_resolve_setup_editor` line 67) and `Optional` is already imported.
- [x] [Functional] No CLI help/snapshot test asserts the old `--agent` default string (verified via git grep over `tests/`).
- [x] [Functional] `resume` already defaults `agent` to `None`; it is explicitly out of scope for this slice.

## Implementation Plan

The `--agent` option cannot keep a plain string default and also detect "the user did not pass `-a`": Typer cannot distinguish an explicit value equal to the default from the default itself. The fix is to default the option to `None` and resolve the effective agent at call time via a new module-level helper mirroring `_resolve_yolo`.

**D1 (Logic).** Add `_resolve_agent(agent: Optional[str], pipeline: bool) -> str` next to `_resolve_yolo` in `src/teddy_executor/__main__.py`: an explicit value always wins; otherwise pipeline runs resolve to `assistant` and every other run to `pathfinder`. This is a pure, additive function with no caller yet, so it is Green-to-Green. Unit tests live in `tests/suites/unit/adapters/inbound/test_start_agent_resolution.py`, following the `_resolve_yolo` pattern in `test_yolo_default_resolution.py`.

**D2 (Wiring).** In the `start` command, change `agent: str = typer.Option("pathfinder", ...)` to `agent: Optional[str] = typer.Option(None, ...)` with updated help text, and pass `agent=_resolve_agent(agent, pipeline)` into `handle_new_session(...)`. The `resume` command — its `agent` option and its `handle_resume_session(...)` call — is left completely untouched. Because the two README default-agent statements become false the moment this behavior lands, they are updated in the SAME commit (atomicity note). The acceptance test `tests/suites/acceptance/test_pipeline_default_agent.py` drives `["start", "-p", "-m", <msg>]` and `["start", "-m", <msg>]` through the `CliTestAdapter` and asserts `Agent Name: Assistant` / `Agent Name: Pathfinder` respectively, mirroring `test_mrp_prompt_assembly.py`'s fake-LLM setup and ensuring the pipeline loop terminates cleanly.

**D3 (Cleanup).** Update `docs/architecture/adapters/inbound/cli.md` (As-Built) to document the deferred `--agent` default and the pipeline-mode `assistant` default.

**Seams.** `agent: str` -> `Optional[str]` is a local signature change confined to the `start` function body; `_resolve_agent` is a brand-new module-local function. Neither is a Shared Seam (`git grep` for either has zero external callers), so the whole slice is Green-to-Green with no breaking-sequence partition.

## Deliverables

- [x] **Logic** - Add `_resolve_agent(agent: Optional[str], pipeline: bool) -> str` next to `_resolve_yolo` in `src/teddy_executor/__main__.py` (explicit value wins; else `assistant` if `pipeline` else `pathfinder`). Add `tests/suites/unit/adapters/inbound/test_start_agent_resolution.py` with the four-cell resolution matrix. Additive, no caller -> Green-to-Green.
- [ ] **Wiring** - In the `start` command, defer the `agent` default to `None` via `typer.Option(None, ...)` with pipeline-aware help text, and pass `agent=_resolve_agent(agent, pipeline)` to `handle_new_session`. Update the two README default-agent statements in the SAME commit. Add `tests/suites/acceptance/test_pipeline_default_agent.py` proving `start -p -m` selects Assistant and `start -m` selects Pathfinder. Leave `resume` untouched. Tracer Bullet / final behavioral gate.
- [ ] **Cleanup** - Update `docs/architecture/adapters/inbound/cli.md` (As-Built) to document the deferred `--agent` default and the pipeline-mode `assistant` default.

## Implementation Notes

### D1 — Add the `_resolve_agent` resolution helper (Logic)

**Production change.** `src/teddy_executor/__main__.py`: added a private module-level `_resolve_agent(agent: Optional[str], pipeline: bool) -> str` immediately after `_resolve_yolo`, co-locating the three resolution helpers at the top of the module. The helper returns `agent` verbatim when it is not `None` (an explicit `--agent` / `-a` always wins); otherwise it returns `"assistant"` when `pipeline` is set and `"pathfinder"` for every other run. It is pure and config-independent — it never consults `IConfigService`. `Optional` and `IConfigService` were already imported, so no import change was needed.

**Test change.** `tests/suites/unit/adapters/inbound/test_start_agent_resolution.py` (new): a four-cell `pytest.mark.parametrize` matrix (`(None, False) -> pathfinder`, `(None, True) -> assistant`, `("architect", False) -> architect`, `("architect", True) -> architect`) plus a `test_resolve_agent_explicit_pathfinder_wins_in_pipeline_mode` edge case proving an explicit `-a pathfinder` is NOT overridden by the pipeline default. The file mirrors the `_resolve_yolo` pattern in `test_yolo_default_resolution.py`.

**Red-Green evidence.** Red (Turn 5): `uv run pytest tests/suites/unit/adapters/inbound/test_start_agent_resolution.py -q` failed at COLLECTION with `ImportError: cannot import name '_resolve_agent' from 'teddy_executor.__main__'` (`1 error in 0.84s`) — no test executed, proving the helper was genuinely absent (greenfield). Green (Turn 6): after the single additive EDIT, the targeted run returned `5 passed`.

**Green-to-Green.** D1 is a brand-new module-local function with NO caller yet (wiring the `start` command is D2), so the change is additive and cannot regress the suite. The Phase 2 Refactor heuristic surfaced no local refactor opportunity and no `[DEBT]`.

**Integration.** The Phase 3 full-suite gate (Turn 7, `make test`, no filters, observed via a redirect + explicit exit-code echo + `exit 0` wrapper to sidestep the EXECUTE-harness false-positive `Interactive prompt detected` sentinel) returned `1723 passed, 5 skipped` — the committed baseline plus D1's five net-new test functions. No regressions.

## Verification

1. `uv run pytest tests/suites/unit/adapters/inbound/test_start_agent_resolution.py` passes with all four matrix cells.
2. `uv run pytest tests/suites/acceptance/test_pipeline_default_agent.py` passes.
3. `teddy start --help` shows the updated `--agent` help text ("Defaults to 'pathfinder' ('assistant' in pipeline mode).").
4. Manual: `teddy start -p -m "..."` selects `assistant` (`Agent Name: Assistant` / metadata `agent_name: assistant`).
5. Manual: `teddy start -m "..."` (no `-p`) still uses `pathfinder` (`Agent Name: Pathfinder`).
6. Manual: `teddy start -a architect -p -m "..."` — the explicit `-a` wins (agent is `architect`).
7. Manual: `teddy resume -p -m "..."` on an existing session leaves its agent unchanged (resume is out of scope).
8. `make test` (full suite, no filters) is GREEN; no pre-existing test regresses, and any test asserting the OLD pipeline default is updated (never weakened).
