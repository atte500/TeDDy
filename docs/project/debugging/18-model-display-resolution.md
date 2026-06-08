# Bug: Model Display Line Redundancy
- **Status:** Resolved
- **Milestone:** [02-stability-and-polish](/docs/project/milestones/02-stability-and-polish.md)
- **Vertical Slice:** [N/A]
- **Specs:** [Stability & Bug Fixes](/docs/project/specs/stability-and-bugfixes.md)

## Symptoms
`teddy start --model openrouter/deepseek/deepseek-v4-pro:nitro` outputs two separate lines for the model:
- `• Model: openrouter/deepseek/deepseek-v4-pro:nitro`
- `• Actual model: deepseek/deepseek-v4-pro-20260423`

Expected behavior: The `• Model:` line should display the actual resolved model (e.g., `deepseek/deepseek-v4-pro-20260423`), and the `API key valid! Model:` should also display the actual model. The separate `• Actual model:` line must be removed.

## Context & Scope
### Regressing Delta
The `• Actual model:` line was introduced as part of the provider routing and display feature. The line is generated in the CLI formatter or session metadata output. The exact commit needs to be identified.

### Environmental Triggers
Only occurs when the model is overridden/aliased (e.g., using `:nitro` or `:floor` shortcuts), which causes the LLM to resolve to a different actual model name.

### Ruled Out
- Not related to session execution logic.
- Not related to plan parsing.

## Diagnostic Analysis
### Causal Model
The `PlanningService._display_telemetry` (line ~200) outputs `• Model:` with the *input* model from config or CLI flag (e.g., `openrouter/deepseek/deepseek-v4-pro:nitro`). After the LLM call, the `generate_plan` method outputs a separate `• Actual model:` line with `response.model` (e.g., `deepseek/deepseek-v4-pro-20260423`) because the telemetry line cannot be overwritten. This redundant line was added to show the resolved model. However, `PromptManager.update_meta` already persists `response.model` into `meta.yaml`'s `model` key. On subsequent turns, `_display_telemetry` reads `meta["model"]` and will show the actual model automatically, making the separate line unnecessary.

### Discrepancies
1. Two model lines (`• Model:` and `• Actual model:`) are displayed. Conflict: The user expects a single `• Model:` line. (Resolved: Remove the `• Actual model:` line; meta.yaml persistence ensures subsequent turns display the actual model.)

### Investigation History
1. Located `• Actual model:` in `planning_service.py:116` via grep. Identified three output points: `planning_service.py:116` (redundant), `planning_service.py:205` (primary), and `session_cli_handlers.py:167` (startup check).
2. Read source files to understand the flow: `model` parameter is the input override/config model; `response.model` is the resolved serving model from the LLM.
3. Analyzed meta.yaml persistence: `PromptManager.update_meta` saves `response.model` to `meta["model"]`, so future turns will display the resolved model in `_display_telemetry`.
4. User confirmed approach: remove the redundant `• Actual model:` line; meta.yaml will handle the update for subsequent turns.

## Solution
### Root Cause
The `• Actual model:` line in `planning_service.py` (lines 114-118) was introduced to show the resolved model after the LLM call, because the `• Model:` telemetry line is printed before the call with the input model. This creates a redundant display.

### Fix
Remove the post-LLM telemetry block that prints the `• Actual model:` line. The resolved model is already persisted to `meta.yaml` by `PromptManager.update_meta` via `meta["model"] = response.model`. On the first turn, `_display_telemetry` will show the input model (from config/CLI). On subsequent turns, it will read the actual model from `meta["model"]` and display it correctly. This eliminates the redundancy without losing the resolved model information.

### Preventative Measures
To prevent this class of issue globally, any future telemetry additions that display post-execution state should first check whether the existing metadata persistence (e.g., meta.yaml) can carry the information to the next turn, avoiding the need for separate inline announcements.
