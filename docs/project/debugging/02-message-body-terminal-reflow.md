# Bug: Message Body Does Not Reflow on Terminal Resize
- **Status:** Resolved
- **Milestone:** Milestone 4: Terminal User Interface (`docs/project/PROJECT.md`)
- **Vertical Slice:** None active; message-body renderer slice `00-20` archived in commit `906cd430`.
- **Specs:** None.

## Symptoms
Expected: after a communicating turn prints its Message body, resizing the terminal reflows the already-visible prose to the new width, exactly as raw terminal output does.

Actual (user report): resizing the terminal leaves the agent's Message text wrapped at the width it was printed at. Long paragraphs stay hard-wrapped and never reflow.

Minimal reproduction: `spikes/debug/message-resize-reflow/01-message-body-wrap-mre.py` renders one long paragraph through the current renderer at console widths 80 and 40 and compares the emitted bytes. Width-dependent newlines inside the paragraph prove the program hard-wraps, which no later resize can undo.

## Context & Scope
### Regressing Delta
`f9b31de1 feat(message-rendering): wire TTY-gated message renderer boundary` (2026-11-17) routed the terminal Message emission through `render_message_body` (`src/teddy_executor/core/utils/message_renderer.py`), implemented by `2afe3154`. Before it, `_print_message_from_teddy` and the interactive ask header echoed the body with raw `typer.secho`/`typer.echo`, i.e. one logical line that the terminal soft-wraps and can reflow. Rich instead lays prose out at `console.width` at print time and emits hard newlines.

### Environmental Triggers
Any TTY where the message is on screen while the user resizes:
- Interactive communicating turn: `ConsoleInteractorAdapter._display_ask_header` (`src/teddy_executor/adapters/outbound/console_interactor.py`) renders the agent body, then `ask_question` waits for a reply — the natural moment to resize.
- Pipeline / `resume -p`: `_print_message_from_teddy` (`src/teddy_executor/core/services/session_orchestrator.py:112`) renders, then the run exits.

Off-terminal (non-TTY) output keeps the raw echo and is unaffected.

### Ruled Out
- Textual TUI rationale pane: `Markdown(id="rationale-content")` receives raw text and is re-laid-out by Textual on resize; it reflows natively.
- Pinned console width: no `Console(width=...)` exists; width is read from the terminal at print time.
- Stale/missing resize handler: none exists in `src/`, and none is needed — the failure is hard-wrapping at print time, not a frozen widget.
- User-reply echo: `emit_user_message` is raw `typer.secho` and already reflows, which is exactly the asymmetry the user notices (their reply resizes, the agent's does not).

## Diagnostic Analysis
### Causal Model
`render_message_body` prints each prose segment as a `rich.markdown.Markdown` renderable. Rich lays the Markdown out at `console.width`: paragraph text is wrapped, and block-level elements (list items, block quotes) are laid out and even cropped at that width. The emitted lines carry hard newlines, which a terminal cannot undo on resize. Crucially, `console.print(..., soft_wrap=True)` only disables the outer wrap/crop; it does not stop Markdown's internal block layout from folding or cropping list items at the console width. A reflowable message must therefore render each prose block at an unbounded width so nothing folds or crops internally, then emit it so the terminal owns the fold.

### Discrepancies
- [x] Raw echo reflows but the rendered agent Message does not (Resolved: the renderer laid prose out at `console.width` and wrote hard newlines plus trailing padding; unbounded layout with trimmed re-emission hands the fold to the terminal).
- [x] Is the TUI the affected surface? No — Textual reflows natively.
- [x] Is `soft_wrap=True` alone a sufficient fix? No — MRE 02 shows paragraphs become width-invariant, but list items are still laid out at console width and at width 40 are cropped to `... should lose ba`, losing data. The culprit is Markdown's internal block layout.
- [x] Can rendering prose at an unbounded width plus terminal-owned emission yield byte-identical, non-cropped output at widths 80 and 40? Yes — probe `04` dumps the emitted bytes: `scratch_strip` is byte-identical at 80/40, keeps the paragraph and both bullets whole, and emits zero padded lines.
- [x] Does the final replica mechanism (unbounded `render_lines` re-emitted as trimmed `Segments`) stay width-invariant and keep production's terminal styles? Yes — MRE `05` passed all 15 checks once probe `06` switched to one joined segment stream with explicit newline separators.
- [x] Does the prose stream need an explicit trailing newline to keep the blank line before a fence? Yes. A bare `Segments` renderable emits no trailing newline, so the joined stream concatenated the fence onto the last bullet (`backticks.\n```bash`); an explicit trailing newline segment restored the blank line, and MRE `05` then passed all 17 checks (Resolved).

### Investigation History
1. Mapped the rendering path across turns 2-4: no `resize` handler and no pinned `Console(width=...)` in `src/`; the agent Message follows `render_message_body` (Rich) while the user reply follows `emit_user_message` (raw `typer.secho`).
2. Identified `f9b31de1`/`2afe3154` as the delta that replaced the raw echo with the Rich renderer.
3. Built the MRE `spikes/debug/message-resize-reflow/01-message-body-wrap-mre.py`; it proved production prose is width-dependent and that `soft_wrap=True` makes a bare paragraph width-invariant.
4. Built the replica proof `spikes/debug/message-resize-reflow/02-soft-wrap-prose-replica-mre.py` on a realistic body (heading, paragraph, bullets, inline code, fenced command). It falsified `soft_wrap=True` as a fix: the paragraph became width-invariant, but list items were still laid out at console width and at width 40 were cropped to `... should lose ba`, losing data. The culprit is Markdown's internal block layout, not only the outer wrap.
5. The probe `spikes/debug/message-resize-reflow/03-prose-wrap-strategy-probe.py` compares prose-wrapping strategies on the realistic body — current, soft-wrap-only, wide-print, and unbounded `render_lines` re-emit — asserting width-invariance, no cropping, marker stripping, and byte-exact fences at widths 80 and 40. It rejected every strategy, which the byte dump later explained.
6. Probe `spikes/debug/message-resize-reflow/04-prose-strategy-dump.py` dumped the real bytes at widths 80 and 40. Production folds paragraphs and pads 8 lines to the console width with trailing spaces (invisible at print time, but a resize re-wraps them into a ragged block). `soft_wrap_only` and `wide_print` leave the second bullet cropped at 40. `render_lines_text` was width-invariant but printed literal `None`, because `Text.rstrip()` returns `None` when nothing needed stripping — a probe bug, not a mechanism failure. `scratch_strip` (render at an unbounded width, rstrip each line, re-emit soft-wrapped) is byte-identical across widths with the paragraph, both bullets, the heading text, and the fenced command intact, and zero padded lines.
7. Rebuilt the sandbox replica `replica_message_renderer.py` on the proven mechanism without the ANSI round-trip: `console.render_lines(..., options.update(max_width=10000), pad=False)` keeps every logical line whole, trailing layout padding is trimmed from the last segments, and each line is re-emitted as `Segments` with `soft_wrap=True` so styles (and hyperlinks) stay native. MRE `05-render-lines-replica-mre.py` validates it against production at widths 80 and 40 plus terminal style parity for bold, inline code, and dim fence delimiters, and passed all 17 checks once probe `06` selected the joined-segment emission and the explicit trailing newline restored the prose/fence separator.
8. Applied the proven fix directly to production: `_emit_prose` and `_trim_trailing_blanks` in `message_renderer.py`, plus four regression tests in `test_message_renderer.py` (width-invariance, no list cropping, no trailing padding, single blank line around fences). The targeted run passed 16 tests and `make test` reported 2537 passed and 5 skipped.
9. Audited the blast radius with `git grep`: `render_message_body` has exactly two production callers (`console_interactor.py`, `session_orchestrator.py`) plus its definition; no production statement prints a rich `Markdown` renderable outside the renderer; and every `display_message` caller passes a short status, error, or summary line, so no long-form body reaches the raw-string print path. No shared port, signature, or data contract moved, so no migration path is required.
10. Added the deterministic structural guard `tests/suites/unit/test_message_prose_reflow_invariant.py`, which walks the installed package and fails when any module other than `core/utils/message_renderer.py` imports `rich.markdown`, so a future surface cannot silently reintroduce print-width hard wrapping.

## Solution
### Root Cause
`render_message_body` printed each prose segment as a `rich.markdown.Markdown` renderable, which Rich lays out at `console.width` and emits with hard newlines, and it left Rich's lines padded to the full console width with trailing spaces. A terminal can only reflow lines it soft-wrapped itself, so an already-printed Message stayed wrapped at its print width, and a narrower resize re-wrapped the invisible padding into a ragged block. The fix lays each prose block out at an unbounded width (`render_lines` with `max_width=PROSE_RENDER_WIDTH` and `pad=False`), trims the trailing layout padding, and re-emits the block as one styled segment stream with explicit newlines under `soft_wrap=True`, so the terminal performs the only fold and owns it thereafter. Proven in the sandbox replica `spikes/debug/message-resize-reflow/replica_message_renderer.py` with MRE `spikes/debug/message-resize-reflow/05-render-lines-replica-mre.py` (17/17 checks), then applied directly to `src/`.

### Affected Components
- `MessageRenderer` (`src/teddy_executor/core/utils/message_renderer.py`): `render_message_body` routes prose through the new `_emit_prose` and `_trim_trailing_blanks`; new `PROSE_RENDER_WIDTH` sentinel; fenced-block emission and `inline_code_theme` unchanged. Fixed directly in production.
- `SessionOrchestrator._print_message_from_teddy` and `ConsoleInteractorAdapter._display_ask_header`: unchanged callers that inherit the reflow behaviour because the renderer signature and contract are unchanged.
- `IUserInteractor.ask_question` and `IRunPlanUseCase` contracts: unchanged; no shared signature or data contract moved, so no migration path is needed.
- Tests: `tests/suites/unit/core/utils/test_message_renderer.py` (four regression tests) and `tests/suites/unit/test_message_prose_reflow_invariant.py` (structural guard).
- Docs: `docs/architecture/core/utils/message_renderer.md` and `docs/architecture/core/services/session_orchestrator.md`.
- Retained evidence: probes `01`-`06` and the replica under `spikes/debug/message-resize-reflow/`.
