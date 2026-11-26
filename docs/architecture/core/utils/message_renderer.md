# Component Design: MessageRenderer
- **Status:** Implemented
- **Classification:** Core Utility
- **Source:** [`src/teddy_executor/core/utils/message_renderer.py`](/src/teddy_executor/core/utils/message_renderer.py)

## Purpose
Renders a communicating turn's Message body to a terminal console: prose through rich `Markdown` laid out at an unbounded width so the terminal owns the fold and a resize reflows it, each fenced block with its own dim verbatim delimiters and syntax colours on the terminal background, and inline code without the default background fill. The caller supplies the console and decides when output is a terminal. The structural guard `tests/suites/unit/test_message_prose_reflow_invariant.py` confines `rich.markdown` imports to this module.

## Consumers
- [SessionOrchestrator](../services/session_orchestrator.md): Calls `render_message_body` and `inline_code_theme` from `_print_message_from_teddy` when the output console is a terminal.
- [ConsoleInteractorAdapter](../../adapters/outbound/console_interactor.md): Calls `render_message_body` and `inline_code_theme` from `_display_ask_header` when the interactive ask console is a terminal.

## Dependencies
- [`split_fenced_segments` and `MessageSegment`](/src/teddy_executor/core/utils/markdown.py): Splits the body into prose and fenced segments that carry their own delimiter lines verbatim.
- `rich` (`Console`, `Markdown`, `Segment`, `Segments`, `Syntax`, `Text`, `Theme`, `DEFAULT_STYLES`): The rendering primitives, including the segment types used to re-emit laid-out lines with their styles intact.

## Class Invariants
None — stateless module-level functions. `PROSE_RENDER_WIDTH` is a module-constant sentinel, not a configurable setting: it exists only to disable Rich's internal fold, so any value beyond a terminal line behaves identically.

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
- **Postconditions:** Prose renders without Markdown markers, laid out at `PROSE_RENDER_WIDTH` and re-emitted as one segment stream with trailing layout padding trimmed and `soft_wrap=True`, so Rich neither folds nor crops the text: the terminal performs the only fold and a resize reflows the visible body. Each fenced block is surrounded by blank lines and bounded by its own dim verbatim delimiters, with its content syntax-coloured and printed `soft_wrap=True` so an over-long line stays unbroken; an empty body prints exactly one newline, matching the raw `typer.secho("")` path.
- **Exceptions:** Normal bodies raise nothing; rich render errors propagate.

Trade-off: terminal-owned wrapping cannot indent a continued line, so a wrapped list item or block quote loses its hanging indentation, and a table wider than the viewport is folded by the terminal instead of aligned by Rich.

### `inline_code_theme() -> Theme`
- **Preconditions:** None.
- **Postconditions:** Returns a `Theme` whose `markdown.code` style keeps colour, bold, dim, italic, underline, and strike but has no `bgcolor`, with every other Markdown style inherited (`inherit=True`).
- **Exceptions:** None.
