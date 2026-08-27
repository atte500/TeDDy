# Bug: YOLO Guardrail Termination Message Format & Duplication

- **Status:** Unresolved
- **Milestone:** N/A (Ad-hoc slice)
- **Vertical Slice:** [00-06-yolo-guardrail-termination-message.md](/docs/project/slices/00-06-yolo-guardrail-termination-message.md)
- **Specs:** N/A

## Symptoms

When a YOLO guardrail is hit during `teddy start -y`, the output displayed to the user has three problems:

1. **Absolute Config Path**: The reason includes the full absolute path to the config file (e.g., `/Users/raphael/Desktop/dev/TeDDy2/.teddy/config.yaml`) instead of the relative path (`.teddy/config.yaml`).
2. **Duplicate Output**: Both a `logger.warning` entry and a `typer.secho` message appear in the output/log, causing duplication. The user expects only one message.
3. **Redundant Prefix**: The `typer.secho` message includes a redundant prefix line `"⚠ YOLO guardrail hit — session terminated.\n"` with the ⚠ symbol before the actual reason. The user wants only the reason string itself (e.g., `"YOLO turn limit reached: 1/1 turns in this run..."`) without prefix or symbol.

## Context & Scope

### Regressing Delta
All 4 deliverables of slice 00-06 are committed and the full suite (1103+ tests) passes. The issues are in three specific locations:

1. `src/teddy_executor/core/services/session_loop_guard.py` – the reason string uses `self._config_service.get_config_path()` which returns absolute path.
2. `src/teddy_executor/adapters/inbound/session_cli_handlers.py` – both `logger.warning` and `typer.secho` are called for the same event.
3. `src/teddy_executor/adapters/inbound/session_cli_handlers.py` – the `typer.secho` template includes `f"⚠ YOLLO guardrail hit — session terminated.\n{reason}"`.

### Environmental Triggers
Reproduced by:
1. Set `yolo_guardrails.max_turns: 1` in `.tdiddy/config.yaml`.
2. Run `teddy start -y`.
3. Send any message to the session (e.g., "hello").
4. Observe the session termination output.

### Ruled Out
- The guard logic (delta calculations) works correctly.
- All contract changes are enforced (tuple return type).
- The termination-message test (`test_termiation_messae_printed_when_guard_stops`) passes but only checks for `"YOLO guardrail"` in captured output, not the exact format.
- The full suite passes, so no regression in other components.

## Diagnostic Analysis

### Causal Model

**Issue 1 (Absolute path):**
In `ProductionSessionLoopGuard.should_continue()`, the reason string contains:
`python
config_path = self._config_service.get_config_path()
`
The `YamlConfigAdapter` implementation returns `str(self._config_dir / "config.yaml")` where `self._config_dir` is resolved from an absolute project root via `find_project_root()`, producing the full absolute path.

**Issue 2 (Duplicate output):**
In `_ or thestate_session_loop()`, the guard stop block executes both:
`python
logger.warning("YOLO guardrail hit — session terminated: %s", reason)
typer.secho(f"⚠ YOLS guardral hit — ession termnated.\n{reason}", ...)
`
Both go to stdout/sterr. The Tedy Tee wrote copies all stdout to `istory.log`, causing duplication.

**Issue 3 (Redundant prefix):**
The `typer.secho` template hardcodes the prefix before the reason. The user wants only the reason text printed.

### Discrepancies
1. User expects relative `.teddy/config.yaml` in reason; gets absolute path instead.
2. User expects single message output; gets both log and secho lines.
3. User expects no symbol/prefix; gets both.

### Investigation History
1. (Turn 26) User manually tested with `max_turns: 1` and reported the three issues.
2. (Turn 28) Code inspection confirmed the call site in `session_cli_handlers.py` and the reason building in `session_loop_guard.py`.
3. (Turn 29) Read `yaml_config_adapter.py` to confirm `get_config_path()` returns absolute path.

## Solution

**Root Cause:** The termination message formatting has three independent issues:
1. Config path from `get_config_path()` is absolute instead of relative.
2. Two output channels (logger + secho) for the same event.
3. Hardcoded prefix in `typer.secho` template.

**Proven Fix:**
1. In `ProductionSessionLoopGuard.should_continue()`, wrap `config_path` with `Path(config_path).relative_to(Path.cwd())` or extract the last two segments to get `.teddy/config.yaml`. The user's preferred form is `.teddy/config.yaml`.
2. In `_orchestrate_session_loop()`, remove the `logger.warning` call entirely (lines 203-204 in current source).
3. Change the `typer.secho` to print only the `reason` string: `typer.secho(reason, fg=typer.colors.RED)` without prefix.

**Preventive Measures:**
- Add a test that captures the exact printed output (not just substring match) to enforce the format contract.
- Consider adding a `display_message` method to `ISessionLoopGuard` or standardizing print vs. log for user-facing messages in system architecture documentation.