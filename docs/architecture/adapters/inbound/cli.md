# Inbound Adapter: CLI

**Status:** Implemented
**Language:** Python 3.9+

## 1. Dependency Injection & Composition Root

**Status:** Planned

To address the complexity in the composition root and decouple the CLI commands from concrete service implementations, we will use a Dependency Injection (DI) container. This is a central part of the [Comprehensive Refactoring Milestone](../../../project/milestones/01-comprehensive-refactoring.md).

-   **Library:** `punq`
-   **Strategy:** A single DI container will be initialized at application startup in `src/teddy_executor/main.py`. It will be responsible for instantiating and wiring all services, adapters, and their dependencies. CLI command functions will then resolve the top-level use case (`ExecutionOrchestrator`) from this container.

### Example Composition Root (`main.py`)

```python
import punq
import typer

# Import services, ports, and adapters
from teddy_executor.core.services import (
    ExecutionOrchestrator,
    PlanParser,
    ActionDispatcher,
    ActionFactory
)
from teddy_executor.core.ports.outbound import (
    IFileSystemManager,
    IUserInteractor
)
from teddy_executor.adapters.outbound import (
    LocalFileSystemAdapter,
    ConsoleInteractorAdapter
)

def create_container() -> punq.Container:
    """Initializes and configures the DI container."""
    container = punq.Container()

    # Register outbound adapters (implementations)
    container.register(IFileSystemManager, LocalFileSystemAdapter)
    container.register(IUserInteractor, ConsoleInteractorAdapter)

    # Register application services
    container.register(ActionFactory)
    container.register(PlanParser)
    container.register(ActionDispatcher)
    container.register(ExecutionOrchestrator)

    return container

# Create the application instance and container
app = typer.Typer()
container = create_container()

@app.command()
def execute(
    # ... typer options ...
):
    """Executes a plan."""
    # Resolve the main service from the container
    orchestrator = container.resolve(ExecutionOrchestrator)

    # Call the service
    report = orchestrator.execute(plan_path=..., interactive=...)
    # ... format and print report ...
```

## 2. Purpose

The CLI adapter is the primary entry point for the `teddy` application. It is responsible for:
1.  Parsing user commands and arguments (`teddy execute`, `teddy context`).
2.  Reading plan content for the execution command from a positional file argument or the clipboard.
3.  Invoking the correct application service via the appropriate inbound port (resolved from the DI container).
4.  Formatting the resulting domain object (`ExecutionReport` or `ProjectContext`) into a user-facing string.
5.  Printing the final output to standard output.

## 3. Used Inbound Ports

This adapter is a "driving" adapter that uses inbound ports to interact with the application core.

*   For plan execution: [`RunPlanUseCase`](../../core/ports/inbound/run_plan_use_case.md), implemented by the `ExecutionOrchestrator` service.
*   For context gathering: [`IGetContextUseCase`](../../core/ports/inbound/get_context_use_case.md) )

## 4. Command-Line Interface

*   **Technology:** `Typer`
*   **Composition Root:** The application's dependency injection and wiring are handled in `src/teddy_executor/main.py` as described in the Dependency Injection section above.

### Session Command: `start`
**Status:** Implemented

Initializes a new session.

*   **Signature:** `teddy start [NAME] [--agent AGENT] [--context PATH]... [--model MODEL] [--provider PROVIDER] [--api-key KEY]`
*   **Behavior:**
    1.  Creates a new session directory in `.teddy/sessions/`.
    2.  If `NAME` is omitted, it uses a temporary ISO-timestamped name.
    3.  Automatically Renames: If created with a timestamped name, the session is renamed to a slugified version of the first generated plan's H1 title.
    4.  Triggers immediate planning and enters the interactive execution loop.
    5.  `--context` / `-c` is repeatable: each occurrence adds one path (e.g., `-c a.py -c b.md`). Comma-separated values within a single occurrence are also split for backward compatibility (`-c "a.py,b.md"`). Limitation: paths containing a literal comma cannot be expressed.

### Editor Validation Preflight

The CLI adapter performs editor validation during session startup (`handle_new_session`, `handle_resume_session`) via `_run_cli_preflight_check()`. When in interactive mode (`interactive=True`), the preflight check calls `_validate_editor_config()` which:

1. Checks if the editor is set to `"disabled"` — if so, skips all validation.
2. Checks if the configured editor exists in `PATH` via `ConsoleToolingHelper.find_editor()`. If found, validation passes.
3. If the editor is missing or unconfigured, displays a warning and discovers available editors via `ConsoleToolingHelper.discover_editors()`.
4. Renders the discovery block: an always-present `Editor Setup` header, then a **bracket**-numbered list (`[1] nvim`, resolved paths hidden), then a single prompt `Select an editor [1-{n}] (number, custom command, or empty to disable): `. A valid number persists the editor's resolved absolute path. A custom command is validated with `which()` and re-prompted if unavailable — it is never accepted without passing validation. Empty input persists `"disabled"`. Invalid/out-of-range input re-prompts.
5. Persists the selection to `.teddy/config.yaml` via `IConfigService.set_setting()` and prints the green confirmation `Editor preference saved to .teddy/config.yaml.`. The full render specification (colours, the fallback branch, and the exact message strings) lives in [spec §4](/docs/project/specs/editor-validation-and-discovery.md).

Editor validation is skipped entirely in non-interactive modes (`--yolo`, `--pipeline`, `--yes`).

### Startup Health Checks (`_run_health_checks`)

`_run_health_checks()` runs two advisory checks on session start/resume (`handle_new_session`, `handle_resume_session`): `_ensure_commit_hooks()` and `_check_git_initialized()`.

**`_ensure_commit_hooks` compare-and-skip (Slice 00-20):** before spawning `pre-commit install -f -t pre-commit -t post-commit`, the guard verifies each requested shim PER HOOK TYPE (pre-commit installs ONE shim per hook type; each declares only its OWN `--hook-type=<type>`): the shim exists in the resolved hooks directory (`.git/hooks` or `core.hooksPath`), contains `hook-impl`, declares `--config=.pre-commit-config.yaml`, declares its own `--hook-type=`, and embeds an existing `INSTALL_PYTHON` path. All shims valid → the subprocess is skipped and the green notification still shows. Any failure (missing shim, dead interpreter, foreign content) → the real install runs exactly as before (safety never reduced). Byte-comparison is explicitly rejected: shims are deterministic functions of (template, INSTALL_PYTHON, args), but install methods (pipx/uv/pip) produce distinct valid hashes, so byte-comparison would trigger a wasteful reinstall on every interpreter change.

### Utility Command: `init`

**Status:** Implemented

Creates the `.teddy/` directory with default files (config, gitignore, init.context), pre-warms heavy imports, and auto-launches `teddy login` if no credentials exist.

- **Signature:** `teddy init`
- **No options** (kept simple).
- **Behavior:**
  1. Calls the existing `InitService.ensure_initialized()` to create `.teddy/` and seed default files.
  2. Pre-warms heavy imports (`litellm`, `trafilatura`, `pyperclip`, `bs4`, `ddgs`, `tiktoken`) by importing them. The tiktoken prewarm eliminates the cold encoding load from the first session turn (2.03s on Windows CI).
  3. Echoes a success message: `"TeDDy initialized in .teddy folder."`
  4. Checks `.teddy/credentials.yaml`. If missing or empty, echoes `"No credentials found. Launching login to OpenRouter..."` and auto-launches the OAuth login browser flow.
  5. **Idempotent:** Safe to run multiple times.

### Main Command: `execute`
**Status:** Implemented

This is the primary command for executing a plan.

*   **Signature:** `teddy execute [PLAN_FILE] [--yes] [--no-copy]`
*   **Input:**
    *   `PLAN_FILE` (Positional Argument, Optional): A path to a Markdown plan file (`.md`).
    *   If `PLAN_FILE` is omitted, the command reads the plan from the system clipboard. This introduces a dependency on the `pyperclip` library.
        *   **Dependency Vetting:** The `pyperclip` library was vetted via a technical spike (`spikes/technical/spike_clipboard_access.py`, now deleted) to confirm its cross-platform reliability, in accordance with the project's third-party dependency standards.
    *   `--yes` (Optional Flag): If provided, the plan will be executed in non-interactive mode, automatically approving all actions.
*   **Behavior (Post-Refactoring):**
    1.  The `typer` command function resolves the `PlanValidator` and `ExecutionOrchestrator` services from the DI container.
    2.  It first invokes the `validator.validate()` method.
    3.  **Validation Failure:** If validation returns errors, execution stops immediately. An `ExecutionReport` is generated with a `VALIDATION_FAILED` status and the list of validation errors.
    4.  **Validation Success:** If validation passes, the command then invokes the `orchestrator.execute()` method, passing the `plan` object and a boolean `interactive` flag (which is `False` if `--yes` is present).
    5.  It receives the `ExecutionReport` domain model in return from either the validation step or the execution step.
    6.  It passes the report to a formatter (`MarkdownReportFormatter`) and prints the final Markdown report to standard output and the clipboard.

### Utility Command: `context`
**Status:** Implemented

This command provides a comprehensive snapshot of the project for an AI agent.

*   **Input:**
    *   `--no-copy` (Optional Flag): If provided, suppresses the default behavior of copying the output to the system clipboard.
*   **Behavior:** It invokes the `ContextService` via the `IGetContextUseCase` port. It receives a `ProjectContext` domain object in return, formats its content, and prints it to standard output while also copying it to the clipboard, as per the standard output handling rules.

### Utility Command: `get-prompt`
**Status:** Implemented

This command provides a convenient way for users to access and override system prompts.

*   **Signature:** `teddy get-prompt <PROMPT_NAME> [--no-copy]`
*   **Input:**
    *   `PROMPT_NAME` (Positional Argument, Required): The name of the prompt to retrieve (e.g., `architect`, `dev`).
    *   `--no-copy` (Optional Flag): If provided, suppresses the default behavior of copying the output to the system clipboard.
*   **Behavior:**
    1.  The command first searches for a custom prompt in the local `.teddy/prompts/` directory. It looks for a file that starts with `<PROMPT_NAME>`, ignoring the file extension.
    2.  If a local override is not found, it falls back to searching for a default prompt in a root-level `/prompts/` directory. The root is identified by searching upwards from the current directory for a `.git` folder.
    3.  If found, the content of the prompt is printed to `stdout` and copied to the clipboard, following the standard output handling rules.
    4.  If the prompt is not found in either location, an error is printed to `stderr` and the command exits with a non-zero status code.

### Auto-Initialization Callback
**)**

The CLI includes a global `bootstrap` callback registered using `app.callback()`. This function is executed by `Typer` before any specific command. Its responsibility is to resolve the `IInitUseCase` from the DI container and invoke `ensure_initialized()`, ensuring that the TeDDy environment is ready for use even on the first run.

### Standard Output Handling

To streamline the interactive user workflow, commands that produce substantial text output (like `context` and `execute`) follow a standard behavior, encapsulated in a private helper function within `main.py`:

1.  The primary output (e.g., project context or execution report) is always printed to `stdout`.
2.  By default, the same output is also copied to the system clipboard using the `pyperclip` library. A confirmation message is printed to `stderr`.
3.  This clipboard behavior is suppressed if the `--no-copy` flag is provided.
4.  If the clipboard is unavailable (e.g., in a headless CI environment), the copy action is silently skipped.

The application exits with a non-zero status code if any action in the `execute` plan fails.

#### Project Context Snapshot
**)**

The `cli_formatter.py` module contains a `format_project_context` function. This function takes the `ProjectContext` DTO and renders its `header` and `content` attributes into a single string. The logic for constructing the detailed content of these strings now resides within the `ContextService`, simplifying the adapter's responsibility to pure presentation.

## 4a. Session Loop Wiring: Interrupt Guard, Quit-Key Listener & Message Injection (As-Built, 2026-10-01; extended 2026-10-02)

### Session-Loop Interrupt Wiring
The shared session loop (`_orchestrate_session_loop`) resolves the container-composed `InterruptGuard` at the boundary, installs its SIGINT handler around the turn loop, and restores the previous disposition once the loop exits (the boundary owns the handler lifecycle). A `KeyboardInterrupt` escaping the turn loop (the WAITING-phase immediate-exit path: prompts and the planning LLM call) is caught at the boundary and surfaced as the `Interrupted by user.` termination notice — nothing is mutated, no report is generated, the process exits cleanly. The notice text is single-sourced from the `INTERRUPT_REASON` constant in `core/utils/interrupt_guard.py` (Bug 56 rewording dropped the now-inaccurate `(Ctrl+C)` fragment, which no longer applied once the bare-`q` quit key and the `resume -p`/`resume -m` paths also terminated the session). The guard is a singleton-scope registration so the boundary's guard and the `OrchestratorPorts` factory's guard are the same instance, sharing the WAITING/EXECUTING phase state and the drain flag.

### Session-Loop Quit-Key Listener Wiring (As-Built, 2026-10-02)
Alongside the guard, the boundary resolves the container-composed `IQuitKeyListener` singleton (Bug 56 bare-`q`) and pairs its `start()`/`stop()` lifecycle with the guard's handler install/restore around the whole turn loop: `start()` runs immediately after `install()`, and `stop()` runs FIRST in the `finally` — before the SIGINT disposition is restored — so no keystrokes are read during restoration. A single bare `q` (no Enter) self-delivers SIGINT so the SAME two-phase WAITING/EXECUTING branch fires: WAITING exits immediately, EXECUTING drains the in-flight action gracefully. The listener is an off-TTY no-op and backs off while another console reader owns stdin.

### `teddy resume -m` Message Injection
The `resume` command accepts `--message/-m` (injected user request/reply without interactive prompting). The flag threads append-only through `handle_resume_session` → `_orchestrate_session_loop` → `orchestrator.resume(..., message=...)` into the lifecycle state machine. The loop clears the injected message to `None` after the first report-bearing iteration so a stale reply cannot re-plan later turns. Consumption semantics: an awaiting-reply turn consumes the message as the user's reply (no plan re-execution, flag cleared, next turn planned with the message); a completed turn gets a smart-fenced `## User Request` appended to the latest report before transitioning.

### Pipeline `start` Message Requirement
`teddy start --pipeline/-p` requires an initial message via `-m/--message`; invoking pipeline mode without one exits with code 1 and the `Pipeline mode requires an initial message via -m/--message.` error. A pipeline turn ending with a MESSAGE action suppresses turn finalization (see `session_orchestrator.md`) and breaks the loop after the report is returned.

### `teddy resume --pipeline/-p` (As-Built, 2026-10-02)
The `resume` command also accepts `--pipeline/-p`, threaded append-only through `handle_resume_session` → `_orchestrate_session_loop` into the orchestrator resume chain (mirroring the `--message/-m` precedent). On an interrupted pipeline MESSAGE turn (awaiting_reply): `resume -p -m "reply"` finalizes turn 01's report (standard message-turn shape, no `## User Request` section), clears the flag, and continues in pipeline mode; `resume -p` without `-m` re-prints the agent MESSAGE (`--- MESSAGE from TeDDy ---`), creates no next turn, and exits again with the flag preserved.

## 5. Plan Parser Factory

The `execute` command is designed to parse plan files written in Markdown. The logic for this resides in the `create_parser_for_plan` factory function within `main.py`, which instantiates the `MarkdownPlanParser`. Legacy support for YAML-based plans has been deprecated and removed.
