# Task: YOLO-by-Default Config Option with `--no-yolo` Override

## Business Goal
Allow users to make `--yolo` (auto-approve) the default mode for sessions via a config setting, while providing an explicit `--no-yolo` / `-n` override to force interactive mode on demand.

## Context

**Origin:** User request — "add yolo by default setting option (also this means having anti yolo flag?)". Agreed to ship this as an ad-hoc Task Brief rather than a Milestone 4 requirement (the requirement has been removed from `docs/project/milestones/04-tui-ux-enhancements.md` and the Roadmap).

**Current behavior:** `--yolo` / `-y` is declared as a plain boolean at three CLI sites in `src/teddy_executor/__main__.py` — `start` (around L120), `resume` (around L375), and `execute` (around L428):

```python
yolo: bool = typer.Option(False, "--yolo", "-y", help="Auto-approve all actions (non-interactive mode).")
```

Each command then computes interactivity as:

```python
interactive = not (yolo or [pipeline or] yes or no_interactive or non_interactive)
```
(`start` around L171, `resume` around L413, `execute` around L453 — `execute` has no `pipeline` term.)

**Desired behavior:** Make the flag tri-state so a config default can participate:
- Flag unset → fall back to the `yolo_default` config value (code default `False`).
- `--yolo` / `-y` → force ON.
- `--no-yolo` / `-n` → force OFF (the "anti-yolo" override), yielding interactive mode unless another non-interactive force (`--yes`, `--pipeline`, `--no-interactive`, `--non-interactive`) is also present.

**Feasibility (verified via a throwaway Typer spike):** only the **combined** dual-flag declaration compiles and resolves correctly:

```python
yolo: Optional[bool] = typer.Option(None, "--yolo/--no-yolo", "-y/-n")
```
→ `[]`→`None`, `--yolo`/`-y`→`True`, `--no-yolo`/`-n`→`False`.
Separate short declarations (`"-y", "-n"`) DO NOT work — `-n` incorrectly maps to `True`. The combined form is mandatory.

**Short-flag availability:** `-n` is currently unused in the CLI entrypoint (existing short flags: `-a`, `-c`, `-m`, `-p`, `-y`), so it is free for use.

**Config surface:** `IConfigService.get_setting(key, default)` supports both plain and dotted keys and returns `default` when the key is absent (see `docs/architecture/core/ports/outbound/config_service.md`). Add a **top-level** `yolo_default: false` key to the shipped template `src/teddy_executor/resources/config/config.yaml`. The code-level default of `False` ensures existing user `.teddy/config.yaml` files (which lack the key) behave unchanged.

**Scope:** Apply the tri-state flag + config default uniformly to all three commands (`start`, `resume`, `execute`) so the mental model is consistent ("`yolo_default` sets the default for the `-y` flag everywhere") and the resolution logic is single-sourced.

**Interaction with guardrails:** When `yolo_default: true`, every session runs non-interactively, so the existing `yolo_guardrails` limits (`max_turns: 99`, `max_session_cost: 5.00`) apply by default. This is intended; no guardrail change is required.

**Single-sourcing (Poka-Yoke):** Resolution MUST be centralized in one helper so the three commands cannot drift.

## Implementation Steps

### Step 1: Add the `yolo_default` key to the shipped config template
- **File:** `src/teddy_executor/resources/config/config.yaml`
- **Change:** Add a top-level `yolo_default: false` entry (immediately above the `yolo_guardrails` section) with a short comment explaining that it sets the default for the `--yolo` / `-y` flag, and that `--no-yolo` / `-n` overrides it per-invocation.

### Step 2: Add a single-sourced resolution helper in the CLI entrypoint
- **File:** `src/teddy_executor/__main__.py`
- **Change:** Add a module-level helper and import `IConfigService` (from `teddy_executor.core.ports.outbound.config_service`) for the type annotation:

```python
def _resolve_yolo(yolo: Optional[bool], config_service: IConfigService) -> bool:
    """Resolve effective YOLO mode. An explicit flag wins; otherwise the config default."""
    if yolo is not None:
        return yolo
    return bool(config_service.get_setting("yolo_default", False))
```

### Step 3: Convert the `start` command to a tri-state flag
- **File:** `src/teddy_executor/__main__.py`
- **Change:** Replace the `start` `yolo` option with:

```python
yolo: Optional[bool] = typer.Option(
    None,
    "--yolo/--no-yolo",
    "-y/-n",
    help="Auto-approve all actions (non-interactive). --no-yolo forces interactive mode.",
)
```
Resolve the config service from the container in the body and use the helper:

```python
config_service = container.resolve(IConfigService)
...
interactive=not (_resolve_yolo(yolo, config_service) or pipeline or yes or no_interactive or non_interactive),
```

### Step 4: Convert the `resume` command to a tri-state flag
- **File:** `src/teddy_executor/__main__.py`
- **Change:** Mirror Step 3 for `resume` (same option conversion; `interactive=not (_resolve_yolo(yolo, config_service) or pipeline or yes or no_interactive or non_interactive)`).

### Step 5: Convert the `execute` command to a tri-state flag
- **File:** `src/teddy_executor/__main__.py`
- **Change:** Mirror Step 3 for `execute` (no `pipeline` term). NOTE: `execute` currently computes `interactive_mode` BEFORE `container = get_container()`; move the computation to AFTER the container is resolved so the config service is available:

```python
container = get_container()
_ensure_project_initialized(container)
config_service = container.resolve(IConfigService)
interactive_mode = not (_resolve_yolo(yolo, config_service) or yes or no_interactive or non_interactive)
```

### Step 6: Add unit tests
- **File:** `tests/suites/unit/adapters/inbound/test_yolo_default_resolution.py` (new)
- **Change:** Cover resolution logic and CLI behavior:
  - `None` + config `yolo_default=False` → `False`; `None` + config `yolo_default=True` → `True`.
  - Explicit `True` / `False` bypass the config value (including explicit `False` overriding a `True` config).
  - CLI-level: with `yolo_default: true`, `start` with no flag runs non-interactively; `start --no-yolo` / `-n` runs interactively; `start --yolo` / `-y` runs non-interactively.
  Use the test harness config mock (`TestEnvironment` / `CliTestAdapter`) and the project's mock-registration helper — no bare `MagicMock` instances.

### Step 7: Update documentation
- **Files:** `docs/architecture/core/ports/outbound/config_service.md`, `docs/architecture/adapters/inbound/cli.md`, `README.md`
- **Change:** Add `yolo_default` to the port doc's "Standard Configuration Keys"; document the tri-state `--yolo/--no-yolo` (`-y/-n`) resolution in the CLI adapter doc; add a short note about the config default + `--no-yolo` to the README's flags section.

## Verification
1. `uv run pytest tests/suites/unit/adapters/inbound/test_yolo_default_resolution.py` passes.
2. Manual: set `yolo_default: true` in `.teddy/config.yaml` — `teddy start` runs non-interactively; `teddy start --no-yolo` and `teddy start -n` prompt interactively.
3. `-y` still forces non-interactive; `-n` is recognized (previously an error).
4. `uv run pytest` (full suite) is green.
5. Pre-existing configs (no `yolo_default` key) behave exactly as before (default `False`).
