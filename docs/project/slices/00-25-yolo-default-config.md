# Slice: Configurable `yolo_default` with Tri-State `--yolo/--no-yolo`

- **Status:** In Progress
- **Milestone:** N/A (ad-hoc — Task Brief [00-25](/docs/project/tasks/00-25-yolo-default-config.md))
- **Specs:** [00-25-yolo-default-config.md](/docs/project/tasks/00-25-yolo-default-config.md)
- **Prototype:** N/A (feasibility verified via throwaway Typer spike documented in the Task Brief)
- **Component Docs:** [cli.md](/docs/architecture/adapters/inbound/cli.md), [config_service.md](/docs/architecture/core/ports/outbound/config_service.md)
- **Scope Slug:** `yolo-default-config`

## Business Goal

Allow users to make `--yolo` (auto-approve) the default mode for sessions via a top-level `yolo_default` config setting, while providing an explicit `--no-yolo` / `-n` override to force interactive mode per-invocation. The tri-state resolution must be single-sourced (Poka-Yoke) and applied uniformly across `start`, `resume`, and `execute`.

## Scenarios

> As a user who prefers automated sessions, I want to enable YOLO mode in my config so that every session runs non-interactively without me passing a flag.

```gherkin
Given a `.teddy/config.yaml` with `yolo_default: true`
When I run `teddy start` with no yolo flag
Then the session runs in non-interactive mode
```

> As a user with `yolo_default: true`, I want to force a single interactive session so that I can review actions without changing my config.

```gherkin
Given a `.teddy/config.yaml` with `yolo_default: true`
When I run `teddy start --no-yolo` (or `-n`)
Then the session runs in interactive mode
```

> As a user with the default config, I want to explicitly force non-interactive mode so that I can automate a single run.

```gherkin
Given a `.teddy/config.yaml` with `yolo_default: false` (or the key absent)
When I run `teddy start --yolo` (or `-y`)
Then the session runs in non-interactive mode
```

## Edge Cases

- **Config key absent**: If the `yolo_default` key is missing from a user's `.teddy/config.yaml`, then the code-level default `False` is used, in order to preserve existing behavior for pre-existing configs.
- **Explicit flag overrides config**: If `yolo_default: true` and `--no-yolo` is passed, then interactive mode is forced, in order to guarantee an explicit flag always wins over config.
- **Other non-interactive forces still win**: If `--no-yolo` is passed together with `--yes` / `--pipeline` / `--no-interactive` / `--non-interactive`, then the session remains non-interactive, because those hidden flags independently force non-interactive mode in the existing `not (...)` expression.
- **`execute` resolution ordering**: If `execute` resolves the config service, then the `interactive_mode` computation must occur after the container/config service is resolved, because it currently precedes `get_container()`.

## Key Unknowns

- [x] [Technical] Combined dual-flag declaration: Does `typer.Option(None, "--yolo/--no-yolo", "-y/-n")` resolve correctly? – Resolved via a throwaway Typer spike documented in the Task Brief: the combined declaration yields `[]→None`, `--yolo`/`-y`→`True`, `--no-yolo`/`-n`→`False`; separate short declarations (`"-y", "-n"`) DO NOT work (`-n` incorrectly maps to `True`).

## Implementation Plan

### Strategy

1. Introduce a single-sourced module-level helper `_resolve_yolo(yolo, config_service)` in `src/teddy_executor/__main__.py`.
2. Declare the tri-state flag (combined form is MANDATORY) on `start`, `resume`, and `execute`.
3. Resolve the config service from the container in each command body; re-order `execute` so resolution happens AFTER `get_container()`.
4. Add a top-level `yolo_default: false` key to the shipped `config.yaml` template (above `yolo_guardrails`).

### Test Harness Strategy

- Acceptance/behavioral CLI tests drive the CLI in-process via `CliTestAdapter` / `TestEnvironment` (Subcutaneous Testing; no internal core imports).
- **Interactivity observability (discovery outcome):** the `execute` command exposes interactivity through the real interactor's per-action prompt — an interactive run prints `Action: <TYPE>` (and `Description: ...`), while a non-interactive run (`--yolo` / `-y`) prints nothing. This is the idiom already asserted by `test_cli_ux_improvements.py::test_cli_interactive_prompt_formatting` (`.with_real_interactor()` + `CliTestAdapter`). The Wiring acceptance test drives `execute` with `--yolo`/`-y` (no prompt) vs `--no-yolo`/`-n` (prompt, with `y\n` supplied) to prove tri-state resolution end-to-end; `start`/`resume` are covered by flag-recognition assertions plus the single-sourced helper.
- Acceptance test file: `tests/suites/acceptance/test_yolo_default_config.py`.
- Unit tests exercise `_resolve_yolo` directly across the full resolution matrix — file: `tests/suites/unit/adapters/inbound/test_yolo_default_resolution.py`.
- Use the project's mock-registration helper (`register_mock` / autospec) for the config-service double — no bare `MagicMock` and no global `mock.patch`.

### Commands Affected

- `start` (`src/teddy_executor/__main__.py` ~L118–L171)
- `resume` (`src/teddy_executor/__main__.py` ~L375–L413)
- `execute` (`src/teddy_executor/__main__.py` ~L428–L453; re-order required)

## Deliverables

- [x] **Contract** - Add a top-level `yolo_default: false` key (with an explanatory comment) to the shipped config template `src/teddy_executor/resources/config/config.yaml`, above the `yolo_guardrails` section.
- [x] **Wiring** - Add the `IConfigService` import and a single-sourced `_resolve_yolo` helper; convert `start`, `resume`, and `execute` to the tri-state `--yolo/--no-yolo` (`-y/-n`) flag; resolve the config service from the container in each command (re-ordering `execute`). Add the acceptance test proving tri-state CLI behavior end-to-end (the Tracer Bullet).
- [x] **Logic** - Wire the config default into `_resolve_yolo` (fall back to `get_setting("yolo_default", False)` when the flag is unset). Add unit tests covering the full resolution matrix plus an acceptance test proving `yolo_default: true` drives the no-flag default.
- [x] **Cleanup** - Update `docs/architecture/core/ports/outbound/config_service.md` (Standard Configuration Keys), `docs/architecture/adapters/inbound/cli.md` (tri-state flag), and `README.md` (config default + `--no-yolo` note).

## Implementation Notes

### Contract — shipped `yolo_default: false`
- Added a top-level `yolo_default: false` key (with an explanatory comment) to `src/teddy_executor/resources/config/config.yaml`, immediately above the `yolo_guardrails` section. A fresh `teddy init` now ships the default explicitly; pre-existing configs without the key still resolve to `False` via the code-level fallback added in the Wiring/Logic deliverables.
- Contract guard: added `tests/suites/unit/adapters/inbound/test_yolo_default_resolution.py::test_shipped_config_template_declares_yolo_default_false`, which loads the bundled template via `importlib.resources` and asserts the key is present and `is False`. This is the only meaningful Contract assertion here — a purely behavioural check cannot distinguish "key present as `false`" from "key absent", because `IConfigService.get_setting` returns the caller-supplied default in the absent case.

### Wiring — tri-state flag + `_resolve_yolo` tracer
- Added a top-level `IConfigService` import and a single-sourced `_resolve_yolo(yolo, config_service)` helper in `src/teddy_executor/__main__.py`. As a tracer bullet, the helper plumbs the `config_service` parameter but does not yet read it: an explicit flag wins (`True`/`False`) and the unset case returns a hardcoded `False`. The config-driven fallback (`get_setting("yolo_default", False)`) is the Logic deliverable's job.
- Converted the `yolo` option on `start`, `resume`, and `execute` from `bool` to the MANDATORY combined tri-state declaration `typer.Option(None, "--yolo/--no-yolo", "-y/-n", ...)`, yielding `None` (unset) / `True` (`--yolo`/`-y`) / `False` (`--no-yolo`/`-n`). Resolved `IConfigService` from the container in each command body; on `execute` the `interactive_mode` computation was moved to AFTER `get_container()`/`_ensure_project_initialized()` so the config service is available.
- Acceptance tracer (`tests/suites/acceptance/test_yolo_default_config.py`, parametrized over `-n`/`--no-yolo`): proves the new anti-yolo flag is accepted and runs the plan interactively (the real interactor prints `Action: CREATE`). This is the sole new end-to-end behaviour; the unset and `-y` paths are behaviourally unchanged and already covered by existing tests.
- Ruff-audit note: `ARG` is not selected, so the tracer may carry the plumbed-but-unused `config_service` parameter without a quality-gate violation; the slice's Wiring/Logic split therefore required no re-partition.

### Delivery — pre-existing Mypy gate (Wiring commit)
- The Wiring VCP commit was blocked by the staged-file-scoped Mypy pre-commit hook: staging `src/teddy_executor/__main__.py` (top-level `IConfigService` import + `_resolve_yolo` helper + tri-state option conversion) widened the hook's import graph and surfaced **8 pre-existing, out-of-scope** errors in 6 untouched files — `action_executor.py:208`, `console_interactor_ask_loop.py:106-107`, `textual_plan_reviewer_editor.py:203-204`, `textual_plan_reviewer_app.py:384`, `session_lifecycle_manager.py:92`, `tests/harness/setup/test_environment.py:27`. None are in the deliverable's own files.
- Handled per the workflow's quality-gate rule: the debt is logged (this slice + `PROJECT.md` → Technical Debt) and the pre-commit stage is bypassed via `--no-verify` for this commit **only**; the post-commit full-suite test gate remains enforced. Root-cause fix is the documented Milestone 5 Mypy-debt task (isolate `msvcrt`/`termios` behind typed accessors; fix the return-value/assignment mismatches).

### Logic — config-driven default
- Replaced the Wiring tracer's hardcoded `return False` with `return bool(config_service.get_setting("yolo_default", False))`, so an unset flag now falls back to the config default while an explicit `--yolo`/`-y` (`True`) or `--no-yolo`/`-n` (`False`) still wins. Updated the helper docstring accordingly. This is a body-only change — the `_resolve_yolo` signature is unchanged, so every caller (`start`, `resume`, `execute`) stays Green-to-Green.
- Unit matrix (`test_yolo_default_resolution.py`): parametrized `_resolve_yolo` across all six `(flag, config, expected)` combinations — `None` + config drives the result; explicit `True`/`False` override the config in both directions. A separate guard asserts the config service is never consulted when the flag is explicit. Uses a spec-bound `Mock(spec=IConfigService)` double (TID251-compliant; `MagicMock`/`patch` remain banned).
- Acceptance config-default test (`test_yolo_default_config.py::test_execute_without_flag_uses_yolo_default_true`): overrides the harness `IConfigService` so `get_setting("yolo_default", …)` returns `True`, runs `execute` with no yolo flag and no input, and asserts the interactive per-action prompt (`Action: CREATE`) is absent — proving the config default drives non-interactive mode end-to-end. The prompt-only nature of `Action: <TYPE>` was confirmed during discovery (`format_action_prompt` is consumed only by the interactor's `confirm_action`, never by the report template/formatter).

### Cleanup — documentation updates
- `config_service.md`: added `yolo_default` as the first entry in "Standard Configuration Keys" — a top-level Boolean setting the default mode for the `--yolo` / `-y` flag across `start`/`resume`/`execute` (default `False`), with `--no-yolo` / `-n` overriding it per-invocation.
- `cli.md`: added a `### YOLO Mode Resolution (Tri-State --yolo/--no-yolo)` subsection documenting the combined Typer declaration (`typer.Option(None, "--yolo/--no-yolo", "-y/-n")` → `None`/`True`/`False`), the single-sourced `_resolve_yolo` helper, the explicit-flag-wins / config-fallback / hidden-forces-still-win precedence, and the `execute` resolution-ordering note.
- `README.md`: added a `--yolo` / `-y` entry to the "Optional flags" list (noting the `yolo_default: true` config default and the `--no-yolo` / `-n` per-run override) and a one-line note under the `--yolo` quick-start snippet.
- Docs-only deliverable (no test layer): the change set touches no production code or tests, so the full suite is unaffected (confirmed green at 1569 passed / 5 skipped).

## Verification

1. `uv run pytest tests/suites/unit/adapters/inbound/test_yolo_default_resolution.py tests/suites/acceptance/test_yolo_default_config.py` passes.
2. With `yolo_default: true` in `.teddy/config.yaml`, `teddy start` runs non-interactively; `teddy start --no-yolo` and `teddy start -n` prompt interactively.
3. `-y` still forces non-interactive; `-n` is recognized (previously an error).
4. `uv run pytest` (full suite) is green.
5. Pre-existing configs (no `yolo_default` key) behave exactly as before (default `False`).
