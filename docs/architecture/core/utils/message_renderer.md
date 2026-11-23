# Component Design: MessageRenderer
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/utils/message_renderer.py`](/src/teddy_executor/core/utils/message_renderer.py)

## Purpose
Renders a communicating turn's Message body to a terminal console: prose through rich `Markdown`, each fenced block with its own dim verbatim delimiters and syntax colours on the terminal background, and inline code without the default background fill. The caller supplies the console and decides when output is a terminal.

## Consumers
- [SessionOrchestrator](../services/session_orchestrator.md): Calls `render_message_body` and `inline_code_theme` from `_print_message_from_teddy` when the output console is a terminal.
- [ConsoleInteractorAdapter](../../adapters/outbound/console_interactor.md): Calls `render_message_body` and `inline_code_theme` from `_display_ask_header` when the interactive ask console is a terminal.

## Dependencies
- [`split_fenced_segments` and `MessageSegment`](/src/teddy_executor/core/utils/markdown.py): Splits the body into prose and fenced segments that carry their own delimiter lines verbatim.
- `rich` (`Console`, `Markdown`, `Syntax`, `Text`, `Theme`, `DEFAULT_STYLES`): The rendering primitives.

## Class Invariants
None — stateless module-level functions.

## Inbound Ports
None — module-level functions, not a port implementation.

## Outbound Ports
None — it writes to the injected `Console` and imports no outbound port.

## Data Contracts
- **`MessageSegment`** (`core/utils/markdown.py`): `kind`, `info`, `content`, `opening`, `closing`. Consumed one segment at a time.
- **`Theme`** (`rich.theme`): Returned by `inline_code_theme`, carrying a single overridden `markdown.code` style.

## Operations

### `render_message_body(body, console) -> None`
- **Preconditions:** `console` is a constructed rich `Console`.
- **Postconditions:** Prose renders without Markdown markers; each fenced block is surrounded by blank lines and bounded by its own dim verbatim delimiters, with its content syntax-coloured and printed `soft_wrap=True` so an over-long line stays unbroken; an empty body prints exactly one newline, matching the raw `typer.secho("")` path.
- **Exceptions:** Normal bodies raise nothing; rich render errors propagate.

### `inline_code_theme() -> Theme`
- **Preconditions:** None.
- **Postconditions:** Returns a `Theme` whose `markdown.code` style keeps colour, bold, dim, italic, underline, and strike but has no `bgcolor`, with every other Markdown style inherited (`inherit=True`).
- **Exceptions:** None.
