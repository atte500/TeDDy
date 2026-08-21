# Bug: Shell Execution TypeError (float + str)
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
Only EXECUTE actions whose plan block includes a `Timeout:` metadata entry (e.g. `- **Timeout:** 10 seconds`) fail with:
`TypeError: unsupported operand type(s) for +: 'float' and 'str'`.

Expected: Shell command executes and returns output regardless of timeout metadata.
Actual: Python TypeError crashes execution when a timeout metadata value is present.

Trigger correlation observed in this session:
- `echo hello` with `- **Timeout:** 10 seconds` -> TypeError float+str.
- `pwd && git rev-parse --show-toplevel` (no timeout) -> SUCCESS.
- Shell-command probes with `- **Timeout:** 30 seconds` -> TypeError float+str.

## Context & Scope
### Regressing Delta
No historical code regression identified yet; the bug reproduces in the current workspace state. The trigger is the presence of a `Timeout:` value in the EXECUTE action's metadata list. Number/format parsing at the action-parse -> execute boundary does not coerce the metadata string into a numeric type before it reaches the shell execution port.

### Environmental Triggers
OS: Darwin 25.5.0 (macOS)
Python: likely 3.11+ (uv project)
The error occurs in the shell execution pathway (shell_adapter or action_executor).

### Ruled Out
- Not a user code issue; it's a framework bug.

## Diagnostic Analysis
### Causal Model
The EXECUTE action parser extracts the `Timeout:` metadata entry as a raw string (e.g. `"10 seconds"`). That string flows uncoerced through `ActionFactory`'s execute protocol into `ShellAdapter.execute(timeout=...)` and finally `subprocess.Popen.communicate(timeout=...)`. CPython's `communicate` computes `deadline = _time() + timeout`, evaluating as `float + str` and raising `TypeError: unsupported operand type(s) for +: 'float' and 'str'`.

Secondary defect: `ActionFactory._handle_execute_protocol` calls `float(default_timeout)` without a try/except, so a malformed config value (e.g. `"30 seconds"`) raises an uncaught `ValueError` instead of falling back to the default.

Both defects share one class: numeric metadata parsed as a string is trusted at the execution boundary without best-effort number coercion ("only read number, otherwise ignore").

### Discrepancies
- `echo hello` should not trigger a float+str error; the command is trivial.
  (Resolved: the crash is not caused by command output parsing; it is triggered by the `Timeout:` metadata string reaching subprocess internals.)
- Commands without a timeout succeed, so the float+str concatenation is not in the generic report formatting path.
  (Resolved: confirmed by `pwd && git rev-parse` success; the trigger correlates exclusively with timeout-bearing actions.)

### Investigation History
1. Static review of ShellAdapter, ActionExecutor, ShellCommandBuilder, ActionFactory. Observation: f-strings used throughout; no local float+str concatenation in these files. Conclusion: the TypeError is raised outside them — either in plan parsing or inside CPython subprocess internals.
2. Environment differential: `echo hello` with Timeout metadata -> TypeError float+str; `pwd && git rev-parse` without timeout -> SUCCESS. Conclusion: crash is triggered by the timeout parameter flow.
3. Direct ShellAdapter call with `timeout="10 seconds"` -> `TypeError: unsupported operand type(s) for +: 'float' and 'str'` with traceback entering `subprocess.py:1204` (`_time() + timeout`). Conclusion: mechanism CONFIRMED. The raw string flows uncoerced from parser → `ShellAdapter` → `Popen.communicate()`.

## Solution
### Root Cause
`action_parser_complex.py:134-135` silently catches `ValueError` from `int(params["timeout"])` with a bare `except ValueError: pass`, leaving the raw string (e.g. `"10 seconds"`) in the params dict. The string flows uncoerced through `ActionFactory` → `ShellAdapter.execute(timeout="10 seconds")` → `Popen.communicate(timeout="10 seconds")`, where CPython computes `deadline = _time() + timeout` → `TypeError: float + str`.

### Systemic Audit
All ad-hoc param conversions in the parsing layer (grep confirmed):

| File | Line | Param | Conversion | Vulnerability |
|------|------|-------|-----------|---------------|
| `action_parser_complex.py` | 82 | `match_all` | `str(params["match_all"]).lower() == "true"` | Safe (string → bool, no try/except needed) |
| `action_parser_complex.py` | 128 | `allow_failure` | `params["allow_failure"].lower() == "true"` | Safe (string → bool) |
| `action_parser_complex.py` | 131 | `background` | `params["background"].lower() == "true"` | Safe (string → bool) |
| `action_parser_complex.py` | 135 | `timeout` | `int(params["timeout"])` (bare except ValueError: pass) | **BUG – uncoerced string leaks** |
| `action_parser_strategies.py` | 35 | `overwrite` | `params["overwrite"].lower() == "true"` | Safe (string → bool) |
| `action_factory.py` | 134 | `default_timeout` | `float(default_timeout)` (config value) | **VULNERABLE – uncaught ValueError on malformed config** |
| `action_factory.py` | 147 | `global_threshold` | `float(global_threshold)` (config value) | **VULNERABLE – uncaught ValueError on malformed config** |

### Generalized Fix Design
A centralized `coerce_action_params(params, type_map)` utility that every parser calls after `parse_action_metadata()`. It applies best-effort coercion for each typed param, removing the param entirely if coercion fails (falling back to system default). The utility uses:
1. Native `int()` / `float()` for clean values.
2. Regex `^(\d+)` / `^(\d+(?:\.\d+)?)` for suffix-bearing strings (e.g. `"10 seconds"`).
3. `str().lower() == "true"` for boolean params.

The same `coerce_param` function is used in `action_factory.py` to protect the `float()` config‑value conversions.

### Implementation Steps
1. **Create `coerce_param` and `coerce_action_params`** in `parser_infrastructure.py` (existing low-level utility module).
2. **Update `parse_execute_action`** to replace the `try/except pass` block with `coerce_action_params(..., {"timeout": int, "tail": int, "allow_failure": bool, "background": bool})`.
3. **Update `parse_edit_action`** to add `coerce_action_params(..., {"match_all": bool})`.
4. **Update `action_parser_strategies.py`** to add `coerce_action_params(..., {"overwrite": bool})`.
5. **Update `action_factory.py`** lines 134 and 147 to use `coerce_param(value, float)` with a fallback default.
6. **Write regression test** that reproduces the original bug (string timeout from plan → no TypeError) and covers secondary config paths.
7. **Run full test suite** to confirm no regressions.