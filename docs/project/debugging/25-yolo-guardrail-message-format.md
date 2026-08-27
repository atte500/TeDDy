# Bug: YOLO Guardrail Termination Message Format, Duplication & Timing

- **Status:** Resolved
- **Milestone:** N/A (Ad-hoc slice)
- **Vertical Slice:** [00-06-yolo-guardrail-termination-message.md](/docs/project/slices/00-06-yolo-guardrail-termination-message.md)
- **Specs:** N/A

## Symptoms

When a YOLO guardrail is hit during `teddy start -y`, the output displayed to the user has four problems:

1. **Guardrail Off-By-One (fires one turn too late)**: With `yolo_guardrails.max_turns: 1`, the session executes turn `[01]` (the seeded initial request) AND turn `[02]` before the guardrail stops it. Expected: stop after turn `[01]`, before turn `[02]` starts. Root-cause hypothesis: `_orchestrate_session_loop` resolves `initial_turn` from the latest turn folder, which already exists (turn `01` seeded by `create_session`), so the first loop iteration computes `turn_delta = 1 - 1 = 0` and continues instead of stopping.
2. **Absolute Config Path**: The reason includes the full absolute path to the config file (e.g., `/Users/raphael/Desktop/dev/TeDDy2/.teddy/config.yaml`) instead of the relative path (`.teddy/config.yaml`). The user wants the final message to say `set 'yolo_guardrails.max_turns' in .teddy/config.yaml.`
3. **Duplicate Output**: Both a `logger.warning` entry and a `typer.secho` message appear for the same event, causing duplication. The user expects only one message (the red `typer.secho` one).
4. **Redundant Prefix + Symbol**: The `typer.secho` message is prefixed with `"⚠ YOLO guardrail hit — session terminated.\n"` and the `logger.warning` with `"YOLO guardrail hit — session terminated: "`. The user wants both to contain only the bare reason string (e.g., `"YOLO turn limit reached: 1/1 turns in this run..."`) — no prefix, no ⚠ symbol.

## Context & Scope

### Regressing Delta
All 4 deliverables of slice 00-06 are committed and the full suite (1103+ tests) passes. The issues are in three specific locations:

1. `src/teddy_executor/adapters/inbound/session_cli_handlers.py` – `_orchestrate_session_loop` resolves `initial_turn` from the latest turn folder name. For a new session, `create_session` has already seeded turn `01` (initial request), so the first loop iteration computes `turn_delta = 1 - 1 = 0`, allowing a second turn to run before the guardrail fires.
2. `src/teddy_executor/core/services/session_loop_guard.py` – the reason string uses `self._config_service.get_config_path()` which returns an absolute path.
3. `src/teddy_executor/adapters/inbound/session_cli_handlers.py` – the guard-stop block calls both `logger.warning(...)` and `typer.secho(...)` for the same event, and both include a redundant prefix (`"YOLO guardrail hit — session terminated: "` / `"⚠ YOLO guardrail hit — session terminated.\n"`).

### Environmental Triggers
Reproduced by:
1. Set `yolo_guardrails.max_turns: 1` in `.teddy/config.yaml`.
2. Run `teddy start -y` (creates a session with the initial request seeded as turn `01`).
3. Send a message to the session (e.g., "hello") — this runs turn `[02]`.
4. Observe: the session terminates only after turn `[02]` completes, with duplicated and prefixed output.

### Ruled Out
- The guard logic (delta calculations) works correctly in isolation.
- All contract changes are enforced (tuple return type).
- The termination-message test (`test_termination_message_printed_when_guard_stops`) passes but only checks for `"YOLO guardrail"` in captured output, not the exact format — so the format, duplication, and timing issues are not caught by the suite.
- The full suite passes, so no regression in other components.

## Diagnostic Analysis

### Causal Model

**Issue 1 (Guardrail fires one turn too late):**
In `_orchestrate_session_loop()` (`session_cli_handlers.py`), `initial_turn` is resolved from `session_manager.get_latest_turn(session_name)` before the loop. For a NEW session, `create_session` has already seeded the initial request as turn `01`, so `initial_turn = 1`. The loop then:
- Iteration 1: `turn_count = 1`, `resume()` processes turn `01`. After the turn, `should_continue(1, ...)` computes `turn_delta = 1 - 1 = 0`, which is `< max_turns` (1), so the loop continues.
- Iteration 2: `turn_count = 2`, `resume()` processes turn `02` (the user's message). After the turn, `turn_delta = 2 - 1 = 1 >= 1`, so the guard stops — one turn too late.

The fix needs to make the baseline 0 for a fresh session (turn `01` is executed within the loop) while keeping the resume baseline at the latest completed turn.

**Issue 2 (Absolute path):**
In `ProductionSessionLoopGuard.should_continue()`, the reason string contains:
```python
config_path = self._config_service.get_config_path()
```
The `YamlConfigAdapter` implementation returns `os.path.join(root_dir, ".teddy/config.yaml")` where `root_dir` is the absolute project root (`find_project_root()`), producing the full absolute path. The final message should display the relative path `.teddy/config.yaml`.

**Issue 3 (Duplicate output):**
In `_orchestrate_session_loop()`, the guard-stop block executes both:
```python
logger.warning("YOLO guardrail hit — session terminated: %s", reason)
typer.secho(
    f"⚠ YOLO guardrail hit — session terminated.\n{reason}",
    fg=typer.colors.RED,
)
```
Both go to stdout/stderr, causing duplication. The user wants only the red `typer.secho` message.

**Issue 4 (Redundant prefix + symbol):**
Both output channels hardcode a prefix (`"YOLO guardrail hit — session terminated: "` for the log, `"⚠ YOLO guardrail hit — session terminated.\n"` for the print). The user wants only the bare reason text, with no prefix and no ⚠ symbol.

### Discrepancies
1. User expects the guardrail to stop before turn `[02]` with `max_turns: 1`; it fires only after turn `[02]` completes.
2. User expects relative `.teddy/config.yaml` in the final message; gets absolute path instead.
3. User expects a single message; gets both log and secho lines.
4. User expects no symbol/prefix; gets both.

### Investigation History
1. (Turn 26) User manually tested with `max_turns: 1` and reported the four issues (timing, absolute path, duplication, prefix/symbol).
2. (Turn 28) Code inspection confirmed the call site in `session_cli_handlers.py` and the reason building in `session_loop_guard.py`.
3. (Turn 29) Read `yaml_config_adapter.py` to confirm `get_config_path()` returns an absolute path when `root_dir` is passed.
4. (Turn 31) Traced the off-by-one: `initial_turn` = latest turn folder (1 for a fresh session) while the first loop iteration executes that very turn, so `turn_delta` is 0 after turn `01`.

## Solution

**Root Cause:** The YOLO guardrail termination has four independent issues:
1. `initial_turn` baseline is off by one for new sessions (turn `01` is seeded before the loop but executed inside it), so the guardrail fires one turn too late.
2. Config path from `get_config_path()` is absolute instead of relative.
3. Two output channels (logger + secho) for the same event.
4. Hardcoded prefixes (`"YOLO guardrail hit — session terminated: "` / `"⚠ YOLO guardrail hit — session terminated.\n"`) in both output channels.

**Applied Fix (2026-08-27):**
1. In `_orchestrate_session_loop()` (`session_cli_handlers.py`, lines 130-144): changed `initial_turn` resolution to `max(0, latest_turn - 1)` when `latest_turn_path` exists. This makes fresh sessions start from 0 (turn 01 seeded by `create_session` becomes delta 1 after the first iteration) while keeping resume baselines correct (latest completed turn - 1 = last completed turn, next turn produces delta 1).
2. In `ProductionSessionLoopGuard.should_continue()` (`session_loop_guard.py`): replaced raw `config_path = self._config_service.get_config_path()` with `rel_path = os.path.relpath(config_path)` in both failure branches, producing `.teddy/config.yaml` instead of the absolute path.
3. In `_orchestrate_session_loop()` (`session_cli_handlers.py`, lines 203-207): removed the `logger.warning(...)` call entirely and changed `typer.secho(...)` to print only the bare `reason` string without the prefix line or ⚠ symbol.

**Preventive Measures:**
- Add a test that captures the exact printed output (not just substring match) to enforce the format contract.
- Add a test asserting the guard stops before the second turn when `max_turns: 1` (loop guard timing).
- Consider adding a `display_message` method to `ISessionLoopGuard` or standardizing print vs. log for user-facing messages in system architecture documentation.