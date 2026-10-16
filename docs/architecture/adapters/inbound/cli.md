# Component Design: CLI Adapter
- **Status:** Implemented
- **Source:** [`src/teddy_executor/__main__.py`](/src/teddy_executor/__main__.py)

## Purpose
The primary inbound (driving) adapter. It parses user commands with `Typer`, resolves use cases and services from the composition root, invokes them through inbound ports, and renders the resulting domain objects to standard output and the clipboard. It owns the process entry point, the shared session startup preamble, and the session execution loop. Helper logic lives in the sibling modules `cli_helpers.py`, `cli_formatter.py`, and `session_cli_handlers.py`.

## Consumers
- The end user, through the `teddy` command-line interface.

## Dependencies
- [`IRunPlanUseCase`](../../core/ports/inbound/run_plan_use_case.md): Drives the `execute` and session `resume` flows.
- [`IGetContextUseCase`](../../core/ports/inbound/get_context_use_case.md): Drives the `context` command.
- [`IInitUseCase`](../../core/ports/inbound/init.md): Runs auto-initialization and the `init` subcommands.
- [`IPlanValidator`](../../core/ports/inbound/plan_validator.md): Drives validation in the manual `execute` flow.
- [`ISessionManager`](../../core/ports/outbound/session_manager.md): Resolves and renames sessions.
- [`ISessionLoopGuard`](../../core/ports/outbound/session_loop_guard.md): Gates the session loop.
- [`IConfigService`](../../core/ports/outbound/config_service.md): Reads and persists settings during `init`, `start`, and `resume`.
- [`IMarkdownReportFormatter`](../../core/ports/outbound/markdown_report_formatter.md): Renders the execution report.
- [`ISystemEnvironment`](../../core/ports/outbound/system_environment.md): Reports TTY status for the setup gates.
- `IPromptManager`: Serves the `get-prompt` command. It has no standalone port document.
- `InterruptGuard` and `IQuitKeyListener`: Manage session-loop interrupt handling.

## Class Invariants
- `single_source_agent_resolution`: The effective agent is resolved only through `_resolve_agent(agent, pipeline)`; the flag is declared deferred so "passed" and "omitted" are distinguishable.
- `single_source_yolo_resolution`: The tri-state `--yolo/--no-yolo` flag resolves only through `_resolve_yolo(yolo, config_service)`, which falls back to `yolo_default` when unset.
- `pipeline_is_non_interactive`: A `--pipeline` run forces non-interactive mode and defaults to the `assistant` agent.
- `resume_agent_is_explicit`: `resume` is excluded from the pipeline agent default so it never silently switches an existing session's agent.
- `shared_startup_preamble`: `start` and `resume` run one shared preamble helper so their startup sequence cannot drift.
- `boundary_owns_interrupt_lifecycle`: The session loop boundary installs and restores the SIGINT handler and pairs the quit-key listener lifecycle with it.
- `setup_gates_are_tty_gated`: The API-key and editor prompts run only when a terminal is attached.

## Inbound Ports
None — this is a driving adapter; it consumes inbound ports but exposes none.

## Outbound Ports
None declared directly — the adapter resolves use cases and services from the composition root and consumes them through their ports.

## Data Contracts
- **Commands:** `start`, `resume`, `init`, `execute`, `context`, `get-prompt`, `update`.
- **Flags:** `--agent`/`-a`, `--context`/`-c`, `--model`, `--yolo`/`-y`, `--no-yolo`/`-n`, `--message`/`-m`, `--pipeline`/`-p`, `--no-copy`.
- **Exit codes:** `0` on success; `1` on a startup error or a pipeline run missing `-m`; non-zero when any executed action fails.

## Operations

### `start(NAME, --agent, --context, --model, --yolo/--no-yolo, --message, --pipeline)`
- **Preconditions:** In pipeline mode, `--message` is required.
- **Postconditions:** Creates a session, runs the shared startup preamble, triggers planning, and enters the session loop. An auto-named session is renamed to a slug of the first plan's H1 title.
- **Exceptions:** Exits with code 1 and the `Pipeline mode requires an initial message via -m/--message.` error when pipeline mode is invoked without `-m`.

### `resume([PATH|SLUG], --agent, --message, --pipeline)`
- **Preconditions:** The target session exists.
- **Postconditions:** Resolves the session path-first then by slug, runs the shared preamble, and resumes the turn loop. `--message` injects the user's reply or next request without interactive prompting.
- **Exceptions:** `ValueError` when neither path nor slug resolution finds a session.

### `init()`
- **Postconditions:** Ensures the `.teddy/` directory, pre-warms heavy imports, prints drift advice, and runs the interactive setup gates when a terminal is attached. Idempotent.

### `execute([PLAN_FILE], --yolo/--no-yolo, --no-copy)`
- **Preconditions:** A plan is supplied by a file argument or the clipboard.
- **Postconditions:** Validates the plan, then executes it, and prints the rendered report to stdout and the clipboard.
- **Exceptions:** Returns a `VALIDATION_FAILED` report when validation fails; exits non-zero when any action fails.

### `context(--no-copy)`
- **Postconditions:** Gathers and prints the project context, copying it to the clipboard unless `--no-copy` is set.

### `get-prompt(PROMPT_NAME, --no-copy)`
- **Preconditions:** `PROMPT_NAME` names an available agent prompt.
- **Postconditions:** Prints the composed system prompt (agent content, separator, MRP base prompt).
- **Exceptions:** Prints an error to `stderr` and exits with code 1 when the prompt is unknown.

### Startup preamble helpers
`_run_health_checks`, `_run_cli_preflight_check`, `_start_background_update_check`, `_run_startup_preamble`, and `_handle_startup_error` implement the fixed startup sequence: advisory health checks, the `Checking configurations...` line, drift and update notifications, the shared disable-footer, and the `Agent:`/`Model:` identity block. The editor validation preflight discovers and persists an editor when the session will read the terminal.
