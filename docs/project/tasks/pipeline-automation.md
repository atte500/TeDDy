# Task: Pipeline Automation Flag (`--pipeline`)

## Business Goal
Enable TeDDy to run autonomously in automated pipelines (e.g., bash loops, CI, Makefiles) by adding a `--pipeline` flag that auto-approves all actions, requires an initial message, and cleanly exits as soon as the agent issues a `## Message` (rather than blocking on stdin waiting for user input).

## Context

### Problem
When running `teddy start -a assistant -m "Prompt A" -y`, the session works for one turn but then blocks indefinitely on `stdin` waiting for the next user input. This makes it impossible to run TeDDy in unsupervised pipelines.

The blocking chain:
1. `handle_new_session` → `_orchestrate_session_loop` (while True loop).
2. `orchestrator.resume()` runs one full agent turn (including `## Message`) and returns.
3. The report is printed to terminal.
4. `should_continue` only checks turn count / cost limits — does not know a `## Message` was sent.
5. Loop calls `resume()` again → `SessionLifecycleManager` sees `AWAITING_USER_INPUT` → calls `user_interactor.ask_question(...)` → blocks on stdin forever.

### Approach
- Add a single `--pipeline` / `-p` flag to the `start` command.
- `--pipeline` implicitly sets `interactive=False` (no need to also pass `-y`).
- In `_orchestrate_session_loop`, after each report, scan `report.action_logs` for an action of type `MESSAGE`. If found → break the loop → process exits 0.
- `handle_new_session` validates that `-m` is provided when `--pipeline` is set, since a pipeline cannot prompt for an initial message.
- No changes to inner execution logic (`SessionOrchestrator`, `SessionLifecycleManager`, `SessionLoopGuard`).

### Files to Modify
1. `src/teddy_executor/__main__.py` — Add `--pipeline` option to `start()` function.
2. `src/teddy_executor/adapters/inbound/session_cli_handlers.py` — Modify `handle_new_session` and `_orchestrate_session_loop`.

---

## Implementation Steps

### Step 1: Add `--pipeline` flag to `start` command
- **File:** [src/teddy_executor/__main__.py](/src/teddy_executor/__main__.py)
- **Change:** Add a new `typer.Option` parameter `pipeline: bool = typer.Option(False, "--pipeline", "-p", help="Run in pipeline mode: auto-approve actions, requires -m, exits after first ## Message.")` to the `start()` function signature (after the `yolo` parameter, around line 126). Then pass `pipeline=pipeline` in the `handle_new_session(...)` call.

#### `FIND:` (add after `yolo` parameter, after line 127/128)
```
    no_interactive: bool = typer.Option(False, "--no-interactive", hidden=True),
```
#### `REPLACE:`
```
    pipeline: bool = typer.Option(
        False, "--pipeline", "-p", help="Run in pipeline mode: auto-approve, requires -m, exits after first ## Message."
    ),
    no_interactive: bool = typer.Option(False, "--no-interactive", hidden=True),
```

#### `FIND:` (update `handle_new_session` call — find the existing call)
```
    handle_new_session(
        container=container,
        name=name,
        agent=agent,
        interactive=not (yolo or yes or no_interactive or non_interactive),
        no_copy=no_copy,
```
#### `REPLACE:`
```
    handle_new_session(
        container=container,
        name=name,
        agent=agent,
        interactive=not (yolo or yes or no_interactive or non_interactive or pipeline),
        no_copy=no_copy,
        pipeline=pipeline,
```

---

### Step 2: Update `handle_new_session` signature to accept `pipeline` and enforce `-m`
- **File:** [src/teddy_executor/adapters/inbound/session_cli_handlers.py](/src/teddy_executor/adapters/inbound/session_cli_handlers.py)
- **Change:** Add `pipeline: bool = False` parameter to `handle_new_session`. Add a pre-flight check that when `pipeline=True` and `message is None`, raise a user-friendly `ValueError` telling them `-m` is required. Pass `pipeline=pipeline` to the `_orchestrate_session_loop` call.

#### `FIND:` (function signature, around line 120)
```
def handle_new_session(
    container: Container,
    name: Optional[str],
    agent: str,
    interactive: bool = True,
    no_copy: bool = False,
    message: Optional[str] = None,
    additional_context: Optional[list[str]] = None,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
):
```
#### `REPLACE:`
```
def handle_new_session(
    container: Container,
    name: Optional[str],
    agent: str,
    interactive: bool = True,
    no_copy: bool = False,
    message: Optional[str] = None,
    pipeline: bool = False,
    additional_context: Optional[list[str]] = None,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
):
```

#### `FIND:` (message resolution block - find the block that checks `if message is None:` around line 173)
```
        # 2. Resolve message first if missing
        if message is None:
            message = user_interactor.ask_question("What are we working on?")
            if not message:
                raise EOFError("No terminal input provided for initial message.")
```
#### `REPLACE:`
```
        # 2. Resolve message first if missing
        if message is None:
            if pipeline:
                raise ValueError(
                    "Pipeline mode requires an initial message via -m/--message."
                )
            message = user_interactor.ask_question("What are we working on?")
            if not message:
                raise EOFError("No terminal input provided for initial message.")
```

#### `FIND:` (`_orchestrate_session_loop` call - find the existing call around line 188)
```
        _orchestrate_session_loop(
            container=container,
            session_name=Path(session_dir).name,
            interactive=interactive,
            no_copy=no_copy,
        )
```
#### `REPLACE:`
```
        _orchestrate_session_loop(
            container=container,
            session_name=Path(session_dir).name,
            interactive=interactive,
            no_copy=no_copy,
            pipeline=pipeline,
        )
```

---

### Step 3: Update `_orchestrate_session_loop` to accept `pipeline` and break on `## Message`
- **File:** [src/teddy_executor/adapters/inbound/session_cli_handlers.py](/src/teddy_executor/adapters/inbound/session_cli_handlers.py)
- **Change:** Add `pipeline: bool = False` parameter to `_orchestrate_session_loop`. After each report is handled, if `pipeline` is True, scan `report.action_logs` for an action with `action_type == "MESSAGE"`. If found, break the loop (process exits cleanly). Add the necessary import for `ActionLogEntry` if needed.

#### `FIND:` (function signature of `_orchestrate_session_loop`, around line 90)
```
def _orchestrate_session_loop(
    container: Container,
    session_name: str,
    interactive: bool,
    no_copy: bool,
) -> None:
```
#### `REPLACE:`
```
def _orchestrate_session_loop(
    container: Container,
    session_name: str,
    interactive: bool,
    no_copy: bool,
    pipeline: bool = False,
) -> None:
```

#### `FIND:` (the turn loop — find `should_continue, guard_reason` block around line 120)
```
        cumulative_cost = float(report.metadata.get("cumulative_cost", 0.0))
        should_continue, guard_reason = loop_guard.should_continue(
            turn_count, cumulative_cost, interactive
        )
        if not should_continue:
            reason = guard_reason or "YOLO guardrail limit reached."
            lines = reason.lstrip("\n").split("\n", 1)
            typer.secho("")
            typer.secho(lines[0], fg=typer.colors.RED)
            if len(lines) > 1:
                typer.secho(lines[1])
            break
```
#### `REPLACE:`
```
        cumulative_cost = float(report.metadata.get("cumulative_cost", 0.0))
        should_continue, guard_reason = loop_guard.should_continue(
            turn_count, cumulative_cost, interactive
        )
        if not should_continue:
            reason = guard_reason or "YOLO guardrail limit reached."
            lines = reason.lstrip("\n").split("\n", 1)
            typer.secho("")
            typer.secho(lines[0], fg=typer.colors.RED)
            if len(lines) > 1:
                typer.secho(lines[1])
            break

        # Pipeline mode: exit cleanly after the first ## Message
        if pipeline and report.action_logs:
            for log_entry in report.action_logs:
                action_type = getattr(log_entry, "action_type", None) or ""
                if action_type.upper() == "MESSAGE":
                    break  # break inner for
            else:
                continue  # no MESSAGE found, continue loop
            break  # MESSAGE found, exit session loop
```

> **Note:** The `else: continue` on the `for` loop ensures we only break the outer loop when a MESSAGE is found. If no MESSAGE exists in the logs, the session continues normally.

---

## Verification

1. **Unit test (recommended):** Write or update a test in `tests/suites/unit/adapters/inbound/test_session_cli_handlers.py` that calls `handle_new_session` with `pipeline=True` and no `-m`, asserting it raises `ValueError`.

2. **Unit test (recommended):** Write or update a test for `_orchestrate_session_loop` with `pipeline=True` and a mock report containing a MESSAGE action log entry, asserting the loop breaks after one iteration.

3. **Manual smoke test (simulated pipeline):**
   ```bash
   teddy start -a assistant -p -m "Say hello and then ask me how I am." -c 'docs/templates/prospect-dossier-template.md'
   ```
   Expected: The agent prints the report (including `## Message`), the process exits with code 0. No blocking on stdin.

4. **Manual error test (missing `-m`):**
   ```bash
   teddy start -a assistant -p
   ```
   Expected: Error message "Pipeline mode requires an initial message via -m/--message." and exit code 1.

5. **Regression test (existing behavior unchanged):**
   ```bash
   teddy start -a assistant -m "Say hello" -y
   ```
   Expected: Works exactly as before (no `--pipeline` flag, so no MESSAGE-detection exit).
