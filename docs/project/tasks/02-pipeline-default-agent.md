# Task: Pipeline Mode Defaults to the Assistant Agent

## Business Goal

Make `teddy start --pipeline` (`-p`) runs default to the action-first **Assistant** agent so automated / CI invocations begin executing immediately instead of opening with Pathfinder's discovery-and-alignment loop.

## Context

Today the `teddy start` command's `--agent` / `-a` option hard-codes a single default of `"pathfinder"` regardless of whether `--pipeline` / `-p` is set (`src/teddy_executor/__main__.py:167-168`). Pipeline mode is the automation path: it auto-approves actions, requires `--message` / `-m`, and exits after the first `## Message`. The harness/workflow backlog entry **[S4]** mandates that pipeline runs default to the `assistant` agent, whose prompt already implements action-first execution (Phase 1, no pre-execution alignment Message — landed under the same backlog item).

The `--agent` option cannot keep a plain string default and also detect "the user did not pass `-a`": Typer cannot distinguish an explicit value equal to the default from the default itself. The fix is to default the option to `None` and resolve the effective agent at call time — an explicit `-a` always wins; otherwise pipeline runs resolve to `assistant` and every other run to `pathfinder`.

> **Path correction:** the backlog's file-by-file spec cites `src/teddy_executor/cli/commands/run.py` and `teddy run -p`. Neither exists. The real seam is the `start` command in `src/teddy_executor/__main__.py`, invoked as `teddy start -p`.

**Deliberate scope — `start` only.** The `resume` command is intentionally left unchanged. Its `--agent` / `-a` is already `Optional[str]` defaulting to `None`, and it means "switch persona for an existing session". Silently defaulting `resume -p` runs to `assistant` would unexpectedly switch an already-established session's agent. Do NOT change `resume` behavior in this task.

**Atomicity note.** The `README.md` statements documenting the default agent become false the moment this behavior lands, so the two README lines MUST be updated in the SAME commit as the code change — never ahead of it.

## Implementation Steps

### Step 1: Add the agent-resolution helper
- **File:** [src/teddy_executor/__main__.py](/src/teddy_executor/__main__.py)
- **Change:** Add a private module-level helper next to the existing `_resolve_yolo` / `_resolve_setup_editor` helpers (`Optional` is already imported):

~~~~~~
def _resolve_agent(agent: Optional[str], pipeline: bool) -> str:
    """Resolve the effective agent name (single-sourced across commands).

    An explicit ``--agent`` / ``-a`` value always wins. When the flag is
    unset, pipeline runs default to the action-first ``assistant`` agent;
    every other run defaults to ``pathfinder``.
    """
    if agent is not None:
        return agent
    return "assistant" if pipeline else "pathfinder"
~~~~~~

### Step 2: Defer the `start` agent default and resolve it
- **File:** [src/teddy_executor/__main__.py](/src/teddy_executor/__main__.py)
- **Change:** In the `start` command, replace the hard-coded `str` default of the `agent` option with a deferred `Optional[str]` default, and resolve it before the handler call. Replace exactly:

~~~~~~
    agent: str = typer.Option(
        "pathfinder", "--agent", "-a", help="Agent prompt to use."
    ),
~~~~~~

with:

~~~~~~
    agent: Optional[str] = typer.Option(
        None,
        "--agent",
        "-a",
        help=(
            "Agent prompt to use. Defaults to 'pathfinder' "
            "('assistant' in pipeline mode)."
        ),
    ),
~~~~~~

Then in the `handle_new_session(...)` call, replace `agent=agent,` with `agent=_resolve_agent(agent, pipeline),`. Leave the `resume` command — its `agent` option and its `handle_resume_session(...)` call — completely untouched.

### Step 3: Update the README to document the pipeline default
- **File:** [README.md](/README.md)
- **Change:** Update the two statements that claim the default agent is always `pathfinder`:
    - Replace:

~~~~~~
If you omit `-a`, the `pathfinder` agent is used by default. Pass just an initial message:
~~~~~~

with:

~~~~~~
If you omit `-a`, the `pathfinder` agent is used by default (the `assistant` agent is used by default in pipeline mode — see `--pipeline`). Pass just an initial message:
~~~~~~

    - In the "Optional flags" list, replace:

~~~~~~
- `--agent` / `-a` – Choose an agent persona (e.g., `pathfinder`, `architect`, `developer`). Default: `pathfinder`.
~~~~~~

with:

~~~~~~
- `--agent` / `-a` – Choose an agent persona (e.g., `pathfinder`, `architect`, `developer`). Default: `pathfinder` (`assistant` in pipeline mode).
~~~~~~

### Step 4: Add a RED-first unit test for the resolution helper
- **File:** [tests/suites/unit/adapters/inbound/test_start_agent_resolution.py](/tests/suites/unit/adapters/inbound/test_start_agent_resolution.py) (new)
- **Change:** Write the test first (RED), following the existing `_resolve_yolo` pattern in `tests/suites/unit/adapters/inbound/test_yolo_default_resolution.py`. Import `_resolve_agent` from `teddy_executor.__main__` and assert:
    - `_resolve_agent(None, False) == "pathfinder"`
    - `_resolve_agent(None, True) == "assistant"`
    - `_resolve_agent("architect", False) == "architect"`
    - `_resolve_agent("architect", True) == "architect"`

### Step 5: Add a public-boundary test proving the CLI wiring
- **File:** [tests/suites/acceptance/test_pipeline_default_agent.py](/tests/suites/acceptance/test_pipeline_default_agent.py) (new)
- **Change:** Prove the resolved agent actually reaches the handler through the real CLI boundary, mirroring the setup in `tests/suites/acceptance/test_mrp_prompt_assembly.py`. Drive `["start", "-p", "-m", "<msg>"]` through the existing `CliTestAdapter` and assert the Assistant is selected (e.g., the first LLM system prompt begins `Agent Name: Assistant`, or the turn metadata records `agent_name: assistant`); add a companion case proving `["start", "-m", "<msg>"]` (no `-p`) still selects `Agent Name: Pathfinder`. Ensure the fake LLM response lets the pipeline loop terminate cleanly (include a MESSAGE action log or return an empty report) so the test cannot hang.

## Verification

1. `make test` — the full suite passes (Continuous Green State) after the change.
2. `teddy start --help` shows the updated `--agent` / `-a` help text ("Defaults to 'pathfinder' ('assistant' in pipeline mode).").
3. Manual: `teddy start -p -m "list the repo tree"` creates a session whose agent is `assistant` (confirm via the turn metadata `agent_name` or the assembled prompt header `Agent Name: Assistant`).
4. Manual: `teddy start -m "survey the backlog"` (no `-p`) still uses `pathfinder` (`Agent Name: Pathfinder`).
5. Manual: `teddy start -a architect -p -m "..."` — an explicit `-a` wins over the pipeline default (agent is `architect`).
6. Manual: `teddy resume -p -m "continue"` on an existing session leaves its agent unchanged (resume behavior is deliberately out of scope).
7. The new unit tests (Step 4) and the new public-boundary test (Step 5) are green.
8. No pre-existing test regresses: run the full suite and update any test that asserts the OLD default agent for a pipeline run (e.g. CLI help/flag snapshot tests). Do NOT weaken coverage to make them pass.
