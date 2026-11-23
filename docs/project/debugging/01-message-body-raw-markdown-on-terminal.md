# Bug: Message Body Renders as Raw Markdown on the Terminal
- **Status:** Resolved
- **Milestone:** Milestone 4: Terminal User Interface (`docs/project/PROJECT.md`)
- **Vertical Slice:** None active; message-body rendering slice `00-20` archived in commit `906cd430`.
- **Specs:** None.

## Symptoms
Expected: a communicating turn's Message body appears on the terminal as formatted prose, with Markdown syntax markers consumed and fenced blocks visually delimited.

Actual (user report): the agent's Message output on the terminal still shows raw Markdown source, although slice `00-20` shipped a terminal renderer on 2026-11-17.

Reproduction: on a pty, the interactive ask header kept `**Bold**` and inline backticks while the pipeline printer stripped both (`spikes/debug/message-render-gate/02-interactive-ask-header-mre.py`, replica `replica_console_interactor.py`). The permanent regression tests are `tests/suites/unit/adapters/outbound/test_console_interactor_ask_header.py`, with the structural guard `tests/suites/unit/test_message_framing_renderer_invariant.py`.

## Context & Scope
### Regressing Delta
Not a regression. `f9b31de1` wired the TTY-gated renderer boundary and `2afe3154` implemented the renderer (2026-11-17); `906cd430` marked the slice complete. The slice migrated only the pipeline presentation and the `resume -p` reprint.

Formatted emission point: `src/teddy_executor/core/services/session_orchestrator.py:112` (`_print_message_from_teddy`), gated on `Console.is_terminal`. Its call sites are pipeline paths: `session_orchestrator.py:396` (pipeline start) and `session_lifecycle_manager.py:468` (`resume -p` stop-again reprint).

Interactive MESSAGE emission: `src/teddy_executor/adapters/outbound/console_interactor.py:79` (`ConsoleInteractorAdapter._display_ask_header`), reached from `ask_question` (`:66`), the handler every dispatched MESSAGE action is mapped to. Before the fix it echoed the raw Markdown body with `typer.echo(prompt, err=True)` on every path.

### Environmental Triggers
The pipeline branch renders only when `Console.is_terminal` is true; a non-terminal stdout (pipe, redirect) keeps raw Markdown by design. The interactive ask echo was unconditional before the fix: it never rendered, on any terminal. After the fix it renders on a terminal and keeps the raw fallback off-terminal.

### Ruled Out
- Missing feature: the renderer exists and is tested.
- Unwired renderer: `_print_message_from_teddy` calls it, and the pipeline and `resume -p` paths use it.
- Tee defeating TTY detection: `Console.is_terminal` delegates to `file.isatty()`; `_TeeWriter.isatty()` delegates to the original.
- `_print_user_message` printing the agent's body: it prints the user's reply under the `User Message:` label.
- `emit_user_message` rendering: three bare `typer.secho` lines (blank line, `User Message:` label, stripped content).
- `_display_ask_header` running in pipeline mode: pipeline `confirm_and_dispatch` short-circuits before dispatch (`action_executor.py:141`), so `ask_question` is never called in pipeline; no duplicate echo.

## Diagnostic Analysis
### Causal Model
An agent `## Message` is parsed into a single MESSAGE action. In non-pipeline mode, `ActionExecutor.confirm_and_dispatch` skips the confirmation prompt but still dispatches; `ActionFactory._handle_message_protocol` maps the action's `prompt`/`content` into `IUserInteractor.ask_question`, passing the agent's body verbatim. `ConsoleInteractorAdapter.ask_question` calls `_display_ask_header`, which printed the cyan framing and then echoed the body raw through `typer.echo`. That is the interactive terminal emission of the agent's Markdown body, and it bypassed the renderer entirely.

In pipeline mode, `confirm_and_dispatch` short-circuits (line 141) to a synthetic `ActionLog` (agent body in `details`) without dispatching, so `ask_question` never runs. `SessionOrchestrator.execute` then prints the body through `_print_message_from_teddy`, which renders on a terminal and echoes raw otherwise.

The MESSAGE `ActionLog.details` field is polymorphic by producer: the pipeline synthetic log carries the agent body (read by `_print_message_from_teddy`), while the interactive dispatched log and the synthesized awaiting-reply log carry the user's reply (read by `_print_user_message` and the report's `## User Reply`). The three read sites are each consistent with their producer, so the apparent contradiction was not a second defect.

The execution report's `## User Reply` block and `handle_report_output` echo the report artifact verbatim; that is by design and scoped to the report artifact, not the session terminal.

### Discrepancies
- [x] User sees raw Markdown on a terminal (Resolved: the interactive ask header echoed the body raw; the pipeline printer rendered it).
- [x] Does `_print_user_message` surface the agent's body? No — it prints the user's reply under the `User Message:` label (Resolved: Turn 9's probe fed the agent body into the priority-3 fallback artificially).
- [x] Does a communication turn dispatch the MESSAGE action through `ask_question`? Yes in non-pipeline mode; pipeline mode short-circuits before dispatch (Resolved: `action_executor.py:135-152`).
- [x] What does a MESSAGE action log's `details` hold? Polymorphic by producer: pipeline synthetic log = agent body; interactive/synthesized log = user reply (Resolved: `action_executor.py:150`, `session_lifecycle_manager.py:602`).
- [x] Does `_display_ask_header` also run in pipeline mode? No — pipeline short-circuits dispatch, so `ask_question` never runs there (Resolved: `action_executor.py:141`).
- [x] Is the user running a released `teddy` that predates the 2026-11-17 merge? Moot for this defect: the current source still bypassed the renderer on the interactive path, so the leak exists regardless of installed version (Resolved).

### Investigation History
1. Grepped `src/` and `tests/` for Markdown rendering and Message handling: found the renderer modules and the pipeline-mode exit comment; dependencies confirm `rich` and `textual` are declared.
2. Inspected git history: found the message-rendering commit chain (`2ac97560`, `f9b31de1`, `2afe3154`, `906cd430`).
3. Listed the feature commits' files and located the sole formatted call site `session_orchestrator.py:132`; the archived-slice read failed because the slice was deleted per the Archiving Policy.
4. Read the renderer, its component doc, the call-site region, and the pipeline Message handling: the gate is `Console.is_terminal`; the pipeline path breaks after the first Message turn rather than printing the body itself.
5. Enumerated every message-framing site: only `_print_message_from_teddy` (two pipeline call sites) formats; `_print_user_message` handles interactive turns; the report path echoes `## User Reply` raw by design.
6. Ran the pty/pipe probe `01-interactive-message-raw-mre.py`: `_print_message_from_teddy` stripped `**` and inline backticks on a pty, while `_print_user_message` kept both literally on pty and pipe.
7. Read `emit_user_message`: three bare `typer.secho` lines with no renderer. Confirmed `Console.is_terminal` delegates to `file.isatty()`, and `_TeeWriter.isatty()` delegates to the original, so the tee cannot defeat the gate.
8. Read the interactive branch (`session_orchestrator.py:386-404`) and `ExecutionOrchestrator`'s `user_request` guard: a captured message propagates to `user_request` only for non-MESSAGE actions, so priority 3 depends on the action log.
9. Read `ConsoleInteractorAdapter`: `ask_question` calls `_display_ask_header`, which printed the cyan `--- MESSAGE from <agent> ---` framing and echoed the raw body with `typer.echo(prompt, err=True)`. This is the interactive surface for the agent's Message, and it bypassed the renderer entirely.
10. Proved the fix in the sandbox replica (`replica_console_interactor.py` + `02-interactive-ask-header-mre.py`): production pty kept both markers (`prose_rendered: false`); replica pty stripped both, rendered the prose, and emitted ANSI; both pipe runs kept the literal markers, so the non-terminal fallback stayed byte-identical.
11. Read the dispatch chain and log construction: `confirm_and_dispatch` skips confirmation for MESSAGE but dispatches in non-pipeline mode, and short-circuits in pipeline mode; `details` is the agent body in the pipeline synthetic log and the user reply in the interactive/synthesized logs.
12. Applied the proven fix directly: `console_interactor.py` builds a themed stderr console (with an injected-console test seam) and routes `_display_ask_header`'s body through `render_message_body` on a terminal, keeping the raw `typer.echo` fallback. Added regression tests `test_console_interactor_ask_header.py` and the structural guard `test_message_framing_renderer_invariant.py`; `make test` passes.

## Solution
### Root Cause
The interactive MESSAGE presentation bypassed the renderer: `ConsoleInteractorAdapter._display_ask_header` echoed the agent's Markdown body with plain `typer.echo` on every path, while slice `00-20` migrated only the pipeline printer and the `resume -p` reprint to `render_message_body`. Verified in a sandbox replica and fixed directly in production (`console_interactor.py`), with a permanent regression test and a repo-wide structural guard.

### Affected Components
- `ConsoleInteractorAdapter` (`adapters/outbound/console_interactor.py`): `__init__` now builds `Console(theme=inline_code_theme(), stderr=True)` with an optional injected `console`; `_display_ask_header` renders the body on a terminal and keeps the raw `typer.echo` fallback off-terminal.
- `IUserInteractor.ask_question` contract (`core/ports/outbound/user_interactor.py`): signature unchanged; the terminal presentation now renders, the non-terminal bytes are unchanged.
- `ActionFactory` / `ActionExecutor`: unchanged; MESSAGE still maps to `ask_question`, and pipeline mode still short-circuits to the formatted `_print_message_from_teddy`.
- Tests: `tests/suites/unit/adapters/outbound/test_console_interactor_ask_header.py` (two cases) and `tests/suites/unit/test_message_framing_renderer_invariant.py` (structural guard).
- Docs: `docs/architecture/adapters/outbound/console_interactor.md` and `docs/architecture/core/utils/message_renderer.md`.
