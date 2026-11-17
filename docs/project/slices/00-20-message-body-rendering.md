# Slice: Formatted Message Body Rendering
- **Status:** In Progress
- **Milestone:** Ad-hoc (no milestone)
- **Depends On:** None
- **Specs:** [interactive-session-workflow.md](/docs/project/specs/interactive-session-workflow.md)
- **Prototype:** [render_live.py](/spikes/prototypes/message-rendering/render_live.py)
- **Component Docs:** [session_orchestrator.md](/docs/architecture/core/services/session_orchestrator.md)
- **Scope Slug:** `message-rendering`

## Goal
Render the body of a communicating turn with terminal formatting instead of raw Markdown, so prose reads cleanly and fenced commands stay copy-pasteable. The change is confined to the Message emission path and leaves pipeline and redirected output byte-identical.

## Context
Key findings from static code reading and the prototype.

- `SessionOrchestrator._print_message_from_teddy(content)` (`src/teddy_executor/core/services/session_orchestrator.py:103`) is the single source of truth for Message framing: a blank echo, the cyan `--- MESSAGE from TeDDy ---` line, then `typer.secho(content)`. Both the pipeline-start print and `SessionLifecycleManager._consume_awaiting_reply`'s stop-again reprint call it, so one change covers both presentations.
- The framing and the body both go to **stdout**; the helper passes no `err=True`. `ConsoleInteractor.display_message` is a different surface that carries errors and notices and is untouched by this slice.
- `core/utils/markdown.py` already owns the fence grammar: `_FENCE_RE = ^ {0,3}(`{3,}|~{3,})(.*)$`, plus `strip_trailing_open_fence`, which walks the fence structure and compares character and length. Reuse that grammar instead of introducing a second regex dialect.
- Tilde fences are first-class in that grammar, so each delimiter must be re-emitted verbatim rather than synthesized. `probe_tilde_fences.py` compared three strategies over five tilde bodies: synthesizing ` ``` ` changed every tilde block's delimiter character and split a tilde block holding a line that starts with a backtick run into two fences; dropping delimiters lost the boundary entirely; re-emitting each segment's own opening and closing lines preserved fence count, delimiter character, indentation, info-string spacing, and content on every body, including an unclosed block. `strip_trailing_open_fence` behaves identically for tildes: an unclosed tilde opener is removed and a balanced tilde block is returned unchanged.
- `rich` arrives only transitively through `textual` and is not declared in `pyproject.toml`. `.githooks/check_architecture_boundaries.py` lists `bs4`, `ddgs`, `httpx`, `litellm`, `prompt_toolkit`, `pyperclip`, `requests`, `subprocess`, `textual`, `trafilatura`, `typer`, and `yaml` in `_FORBIDDEN_CORE_ADAPTER_LIBS`; `rich` is not among them, so a `core/utils/` renderer needs no new port.
- `rich.console.Console.print` accepts a per-call `width`, so one console can host prose at terminal width and a fence at `max(width, longest_line)` without a second console instance.
- `rich.syntax.Syntax` defaults to the `monokai` theme, whose `background_color` paints a fill behind every token; `background_color="default"` substitutes the terminal's own background and keeps the token colours. `Syntax` also defaults `padding=(0, 1)`, which prepends a space to every line and would corrupt a copy-pasted `FIND:` block.
- `Console.print(str)` runs rich's markup parser. Rich's tag opener matches only a lowercase letter, `#`, `/`, or `@` (`rich.markup.RE_TAGS` = `((\*)\[([a-z#/@][^[]*?)])`, verified by `spikes/prototypes/message-rendering/probe_bracket_tokens.py`). Upper and punctuation tokens — `[TODO]`, `[DEBT]`, `[HOLD]`, `[!]`, `[?]`, `[✓]` — therefore survive on every path, including a bare string print. Lowercase tokens — `[note]`, `[brackets]`, `[i]` as in `array[i]` — are silently consumed by a bare string print; the renderer avoids that by printing only renderables (`Markdown`, `Syntax`, `Text`) and never a bare string.
- `Markdown` treats a line of the form `[label]: url` as a reference-definition and renders nothing for it, independent of rich markup. A Message body carrying such a line loses it silently. The renderer does not mask this; the Developer documents it as expected Markdown behaviour.
- Inline code carries a fill by default: rich's `markdown.code` style is `Style(bold=True, color="cyan", bgcolor="black")`. `probe_theme_and_edges.py` proves the removal at ANSI level with a self-tested SGR parser: the same span emits `\x1b[1;36;40m` under the default theme and `\x1b[1;36m` under a theme whose `markdown.code` entry keeps every attribute except `bgcolor`, with the span text unchanged in both. Fences are unaffected, because `Syntax(background_color="default")` already emits no fill.
- Indented code blocks are the one code path that never reaches `Syntax`: a four-space block does not match `_FENCE_RE`, so it stays in a prose segment and `Markdown` paints it with the code theme's own background (`\x1b[48;2;39;40;34m` under monokai). `markdown.code_block` is not the lever — the fill comes from the code theme, and `ansi_dark` was the only one of five tested themes that rendered an indented block without one. Recorded as a known limitation because Message bodies carry fenced blocks; the remedy, if the case ever matters, is a one-line `Markdown(code_theme="ansi_dark")`.
- Three further rich behaviours are documented rather than overridden. `ImageItem` hoists an image to the start of its paragraph with an emoji prefix, so `before ![alt](url) after` renders with the words intact but out of order. `Heading` centres a level-1 heading across the console width. A GFM task list keeps its `[ ]` / `[x]` checkbox as literal text.
- Test blast radius is three modules asserting on captured non-TTY output: `test_session_orchestrator.py`, `test_session_lifecycle_pipeline_stop_again.py`, and `test_pipeline_message_and_resume_flow.py`. A TTY gate keeps all three green without rewrites.
- Prototype evidence: `render_live.py --only syntax-fenced` prints the accepted treatment; long lines (181-character json, 183-character sql, 155-character handoff) were verified unbroken with no leading space at widths 60, 80, and 100. `probe_bracket_tokens.py` rendered a bracket-token matrix through every candidate path and pinned which forms survive, which are silently consumed, and which are treated by Markdown as reference definitions. `probe_tilde_fences.py` compared delimiter strategies across five tilde bodies and pinned verbatim re-emission as the only strategy that preserves fence count, delimiter character, and content. `probe_theme_and_edges.py` measured the inline-code override at ANSI level with a self-tested SGR parser and compared five code themes on an indented block; `show_markdown_spec.py` rendered a comprehensive Markdown sample through the accepted treatment and probed 22 constructs for whether they render or leak a raw marker.

- Dim delimiter legibility, measured with `probe_dim_legibility.py` under rich 15.0.0: a dim delimiter line emits SGR `2` under `truecolor`, `256`, and `standard` (16-colour). `NO_COLOR=1` and an explicit `no_color=True` console strip foreground and background only, because rich routes the no-colour path through `Segment.remove_color`, which maps each style through `Style.without_color`, so the faint attribute survives and the delimiters keep their literal backticks. `TERM=dumb` resolves `color_system=None` and emits no SGR at all, leaving full-contrast plain backticks. The delimiter text carries the boundary in every configuration; dim is an affordance that degrades to plain text, never to invisibility.

## Scenarios

> As a developer running an interactive session, I want a Message turn rendered with terminal formatting so that prose reads cleanly and fenced commands remain copy-pasteable.

```gherkin
Given a session whose stdout is a terminal
When the agent emits a turn carrying a Message
Then the body's prose renders without ## or ** markers
And each fenced block is delimited by its own dimmed backtick or tilde run
And every fenced line appears unbroken at its original bytes
```

```gherkin
Given a Message body whose fenced block is delimited by tildes
When the turn body is rendered
Then the block keeps its tilde delimiters and its fence count
```

```gherkin
Given a session running with --pipeline or with stdout redirected to a file
When the agent emits a turn carrying a Message
Then the body is emitted as the exact raw Markdown it emits today
```

```gherkin
Given a Message body containing a fenced teddy start command
When the user selects and copies that block
Then the copied text runs as a valid command, with no injected leading space and no folded line
```

```gherkin
Given a pipeline Message turn that stopped awaiting a reply
When the turn is resumed without a reply and the agent's message is reprinted
Then the reprint renders identically to the pipeline-start print
```

## Edge Cases
- **Upper and punctuation tokens**: If prose contains `[TODO]`, `[DEBT]`, `[HOLD]`, `[!]`, `[?]`, or `[✓]`, then the tokens render literally on every path, because none begins with a rich tag-start character.
- **Lowercase tokens**: If prose contains `[note]`, `[brackets]`, or `[i]` (as in `array[i]`), then the tokens render literally only because the renderer prints `Markdown` (a renderable); a bare `console.print(str)` silently consumes them.
- **Markdown reference definition**: If a line begins with `[label]: url`, then `Markdown` renders nothing for that line, because it is consumed as a link reference. Expected Markdown behaviour, not a defect; the Developer documents it rather than masking it.
- **Markdown inline link**: If prose contains `[text](url)`, then `Markdown` renders it as a link showing `text`. Intended behaviour; the visible bytes differ from the raw path, which is acceptable because the raw path is preserved for pipeline output.
- **Inline code**: If prose contains an inline code span, then it renders cyan and bold with no background fill, because the prose console's theme drops rich's default `markdown.code` background and inherits every other style.
- **Indented code block**: If a four-space-indented block appears, then it renders through `Markdown` and keeps the code theme's background fill, because it never matches `_FENCE_RE` and so never reaches `Syntax`. Known limitation; the remedy is recorded in Context.
- **Image syntax**: If prose contains `![alt](url)`, then rich hoists it to the start of the paragraph with an emoji prefix, so the surrounding words survive but their order does not. Known limitation; no substitution is applied, because a regex cannot reliably skip inline code spans.
- **Level-1 heading**: If prose contains `# Title`, then it renders centred across the console width, which is rich's `Heading` behaviour. Accepted; Message bodies use `##` and below for sections.
- **Task list**: If prose contains `- [ ] open`, then the checkbox stays literal `[ ]` text, because rich does not interpret GFM task lists. Accepted.
- **Over-long fenced line**: If a fenced line exceeds the terminal width, then it renders unbroken on a canvas widened to that line, because folding breaks copy-paste.
- **Prose-only body**: If the body contains no fence, then it renders through `Markdown` alone with no delimiter lines.
- **Unknown info string**: If the fence carries an info string `Syntax` cannot resolve into a lexer, then the block falls back to plain text without altering its bytes.
- **Untagged fence**: If the fence carries an empty info string, then it renders as plain text with an unlabelled opening delimiter.
- **Empty fence**: If a fence is opened and immediately closed, then both delimiters render and the content between them is empty.
- **Nested fence**: If a four-backtick fence wraps a three-backtick block, then the block stays a single segment, because the splitter compares fence character and length.
- **Tilde fence**: If a block is delimited by `~~~`, then it renders with `~~~` delimiters, because each segment re-emits its own opening and closing lines instead of synthesizing backticks.
- **Tilde fence holding a backtick run**: If a `~~~` block contains a line that starts with a backtick run, then it stays one block, because the delimiter characters differ; a synthesized backtick opener would be closed by that content line and shatter the block.
- **Unclosed fence**: If the body ends inside an open fence, then the renderer emits the raw opening line and the content with no closing delimiter, so the output mirrors the input instead of inventing one.
- **Redirected stdout**: If `Console.is_terminal` is false, then the raw `typer.secho(content)` path runs unchanged and the three existing assertion modules stay green.
- **Low-colour terminal**: If `NO_COLOR` is set or `TERM` is `dumb`, then rich drops styling but the delimiters remain readable as plain ``` text.
- **Trailing newline**: If the body ends with or without a newline, then the rendered output keeps the same trailing-newline parity as today's `typer.secho(content)`.

## Key Unknowns

- [x] [Functional] Dim-delimiter legibility: Whether `style="dim"` reads as a boundary on a 16-colour or `NO_COLOR` terminal. Resolved 2026-11-17 by `probe_dim_legibility.py` under rich 15.0.0. A 16-colour terminal receives SGR `2`; a `NO_COLOR` terminal loses foreground and background but keeps the faint attribute; `TERM=dumb` drops all styling and leaves plain backticks. The delimiter text carries the boundary in every case, so `style="dim"` stays and the "illegible" branch is unreachable.

## Impact

1. [NEW] `src/teddy_executor/core/utils/message_renderer.py` — renderer entry point that walks the split segments and prints prose and fences, plus `inline_code_theme()`, which returns rich's defaults with the `markdown.code` background cleared.
2. [EXTEND] `src/teddy_executor/core/utils/markdown.py::split_fenced_segments` — additive helper beside `_FENCE_RE`, returning typed segments that carry their own opening and closing delimiter lines, without touching any existing caller.
3. [EXTEND] `pyproject.toml` — declare `rich` as a direct dependency.
4. [MIGRATE] `src/teddy_executor/core/services/session_orchestrator.py::_print_message_from_teddy` — gate the body through the renderer while keeping the blank echo and cyan header untouched.

## Deliverables

- [x] **Env** - Declare `rich` in the `pyproject.toml` dependency list, so the renderer imports a direct dependency rather than a transitive one.
- [x] **Interface** - Add a frozen `MessageSegment` dataclass (`kind`, `info`, `content`, `opening`, `closing`) and `split_fenced_segments(body)` to `core/utils/markdown.py`, reusing `_FENCE_RE` and the fence-character and length rules already encoded in `strip_trailing_open_fence`. `opening` and `closing` carry the raw delimiter lines verbatim, so tilde fences, indented fences, and longer closing runs survive; `closing` is empty for an unclosed final block.
- [x] **Wiring** - Build one `Console(theme=inline_code_theme())` in `_print_message_from_teddy`, keep the blank echo and cyan header untouched, and route the body through the renderer when `console.is_terminal` is true; otherwise emit `typer.secho(content)` exactly as today. The theme keeps `inherit=True` (the `Theme` default), or rich drops every other Markdown style.
- [ ] **Core** - Implement `render_message_body(body, console)` in `core/utils/message_renderer.py`: prose through `Markdown` at terminal width; each fence through a dim `Text` carrying the segment's own `opening` line, `Syntax(content, info or "text", word_wrap=False, padding=(0, 0), background_color="default")`, and the segment's own `closing` line when it exists, each printed with `console.print(..., width=max(console.width, longest_line))` and separated from the surrounding prose by a blank line. Delimiters are never synthesized, so a tilde block stays a tilde block. Export `inline_code_theme()` from the same module: derive rich's default `markdown.code` style, drop `bgcolor`, keep colour, bold, dim, italic, underline, and strike, and return a `Theme` built from it so inline code loses the fill and keeps its weight.

## Implementation Notes

### Env
Declared `rich>=15.0.0,<16` in `pyproject.toml` and refreshed `uv.lock`, which now lists `rich` under `teddy-cli`'s direct dependencies. The bound pins the 15.x line because both `Theme`'s `inherit` default and the no-colour behaviour were measured against rich 15.0.0; a major bump could change either. `uv lock --check` reports the lock current and the resolved version is still 15.0.0, so the declaration changed no resolution. `make test`: 2273 passed, 5 skipped.

### Interface
Added `MessageSegment` (frozen dataclass: `kind`, `info`, `content`, `opening`, `closing`) and `split_fenced_segments(body)` to `core/utils/markdown.py`, above `embed_in_fence`, reusing `_FENCE_RE` unchanged so there is no second fence dialect. The DTO carries the raw `opening` and `closing` lines rather than a synthesized fence, because the tilde probe proved synthesis rewrites the delimiter character and shatters a tilde block holding a backtick run. Closing-fence matching sits in `_closing_fence_index` with one guard per rule (same character, run at least as long, no info string) and prose emission in `_flush_prose`; both are module-level so the splitter carries a single branch and stays well inside the `max-complexity = 9` gate.

Whitespace-only prose runs are dropped by design: the renderer owns the blank spacing around a fence, so a blank line between two blocks carries no information. No runtime contract assertion was added, because the splitter's input is any `str` and has no precondition that could fail; its postconditions — delimiters verbatim, content never closing its own block — are pinned by the contract tests instead.

Contract tests live in the sibling module `test_markdown_segments.py` (18 cases covering prose-only, empty body, tagged/untagged/indented/tilde/longer-closing/unknown-info/trailing-space/CRLF delimiters, surrounding prose, nested four-wrapping-three, unclosed block, mismatched character, empty fence, whitespace-only prose, and DTO immutability) rather than growing `test_markdown_utils.py` past the 300-line file gate. `markdown.py` ends at 275 lines. `make test`: 2291 passed, 5 skipped.

### Wiring
Added `core/utils/message_renderer.py` with the two entry points `_print_message_from_teddy` will call: `render_message_body(body, console)` and `inline_code_theme()`. Both are deliberately skeletons — `render_message_body` prints the whole body as a `Text` renderable and `inline_code_theme()` returns the default `Theme()` — because the Wiring deliverable only proves the boundary connects; the Core deliverable replaces the body with per-segment prose/fence rendering and derives the theme from rich's default `markdown.code` minus its background. The skeleton still prints a renderable rather than a bare string, so rich's markup parser never touches the body and lowercase tokens such as `[i]` survive.

`_print_message_from_teddy` gained an optional `console: Optional[Console] = None` parameter. The addition is additive: both production callers (`session_orchestrator.py:377`, `session_lifecycle_manager.py:418`) keep passing only `content`, and the helper builds `Console(theme=inline_code_theme())` internally when none is injected. That internal console answers `is_terminal`, which gates the body: a terminal routes through `render_message_body`, everything else emits `typer.secho(content)` exactly as before. The injection seam exists because the CLI runs under `CliRunner`, which is non-TTY, so the formatted path is unreachable through the real entry point; it is the only way to pin the terminal branch.

The tracer lives at `tests/suites/unit/core/services/test_message_rendering_wiring.py` (two cases: a `force_terminal=True` recording console receives the body, a non-terminal one keeps it on the raw `typer` path with an empty buffer). `make test`: 2293 passed, 5 skipped — including the three capture-based modules, which confirms the non-TTY branch stayed byte-identical.

## Verification

1. **Accepted rendering:**
   Run `uv run python spikes/prototypes/message-rendering/render_live.py --only syntax-fenced`.
   Verify prose renders without Markdown markers, each fenced block is delimited by its own dimmed delimiter lines, and the handoff command sits on one unbroken line.

2. **Live Message turn:**
   Start a session and let the agent reply with a Message containing one fenced bash block.
   Confirm the terminal shows formatted prose, dimmed delimiters with the language tag, and syntax-coloured code.

3. **Raw fallback:**
   Run the same turn with output redirected, for example `uv run teddy resume -p > /tmp/teddy-raw.txt`.
   Verify the captured body is raw Markdown with literal `**` and ``` markers and no ANSI escapes.

4. **Tilde fidelity:**
   Run `uv run python spikes/prototypes/message-rendering/probe_tilde_fences.py`.
   Verify the `verbatim` rows report the same fence count and the same delimiter character before and after on every body, and that `current` reports a fence count increase with the delimiter character changed on `tilde-holding-backticks`.

5. **Inline-code fill:**
   Run `uv run python spikes/prototypes/message-rendering/probe_theme_and_edges.py`.
   Verify the `default theme` row reports a background fill for each inline span while the `stripped theme` row reports none, and that `text_kept=True` in both rows.
