# Slice: 02-11-AST Parser Resilience

- **Status:** Planned
- **Type:** Feature
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [docs/project/specs/stability-and-bugfixes.md](/docs/project/specs/stability-and-bugfixes.md)
- **Prototype:** [spikes/prototypes/02-11-ast-parser-resilience.py](/spikes/prototypes/02-11-ast-parser-resilience.py)
- **Component Docs:**
  - [MarkdownPlanParser](/docs/architecture/core/services/markdown_plan_parser.md)
  - [Parser Infrastructure](/docs/architecture/core/services/parser_infrastructure.md)

## Business Goal
Make the plan parser resilient to two common LLM formatting artifacts: (1) trailing text on the same line as a closing code fence (6+ backticks or tildes), which contaminates code block content, and (2) unexpected code blocks at the very end of a plan after all actions.

## Scenarios

> As a user, I want trailing text on the same line as a closing fence (e.g., `~~~~~~ trailing text`) to be stripped so that code block content is not contaminated with trailing fence text.
```gherkin
Given a plan whose last action's closing fence has trailing text on the same line
When the plan is parsed
Then the trailing text is stripped from the fence line
And the code block content does not contain the trailing text
```

> As a user, I want an unexpected code block at the end of the plan (after all valid actions) to be silently ignored so that LLM formatting noise doesn't cause a false validation failure.
```gherkin
Given a plan with valid actions followed by a trailing unclosed code block
When the plan is parsed
Then the trailing code block is silently ignored
And the correct actions from the valid part of the plan are returned
```

## Edge Cases
- **Same-line trailing text on OPENING fences**: Already handled by mistletoe (implicitly ignored). Double-cleaning by preprocessing causes no harm.
- **Same-line trailing text on 3/4/5-length fences**: These are not closing fences (length < 6), so they are NOT stripped. This is intentional — shorter fences are less likely to be LLM artifacts and more likely to be legitimate content.
- **Trailing Paragraph node (newline-separated trailing text)**: NOT handled in this slice. The user explicitly chose not to skip trailing Paragraph nodes — validation stays strict.
- **Trailing text inside a legitimate code block that happens to start with 6+ tildes**: This is an acceptable trade-off given the rarity of such content in plan files and the frequency of LLM noise.

## Deliverables
- [ ] **Harness** - Unit test: 6-backtick closing fence with same-line trailing text → stripped from CodeFence content.
- [ ] **Harness** - Unit test: 6-tilde closing fence with same-line trailing text → stripped.
- [ ] **Harness** - Unit test: trailing unexpected CodeFence at end of plan → silently ignored (existing BlockCode/CodeFence skip extended for tail-end).
- [ ] **Logic** - Implement `_FencePreProcessor.process()` to strip same-line trailing text on fence lines of 6+ backticks or tildes (strip trailing non-whitespace content after the fence characters on that line).
- [ ] **Logic** - Add tail-end skip in `_parse_actions` for trailing BlockCode/CodeFence nodes after the last action (consistent with 02-06's between-action skip pattern).
- [ ] **Wiring** - Acceptance test: plan with both same-line trailing text on closing fence AND trailing codeblock → SUCCESS with correct action content.

## Implementation Notes
(To be filled by the Developer as implementation proceeds.)

## Implementation Plan
### Changes Required

**File 1: `src/teddy_executor/core/services/parser_infrastructure.py`**
- Replace the pass-through `_FencePreProcessor.process()` with the validated trailing-text stripping logic (prototype-proven via `strip_trailing_fence_text`).
- **Regex Pattern:** Use `r"^(\s*)(\~{6,}|\`{6,})(.*)$"` — matches optional leading whitespace, then 6+ pure tildes OR 6+ pure backticks, then any trailing content.
- **Mixed-Fence Guard:** Before stripping, check that trailing content does NOT contain backtick or tilde characters (`any(c in trailing for c in ("`", "~"))`). This prevents corrupting lines like `~~~~~~\` trailing` where fence characters appear in the trailing content.
- **Edge Cases Handled:**
  - Fences with 3-5 chars (e.g., `~~~~`, ``````) are NOT modified (sub-threshold safety)
  - Indented fences preserve leading whitespace (`    ~~~~~~ text` → `    ~~~~~~`)
  - Immediately adjacent trailing text is stripped (`~~~~~~python` → `~~~~~~`)
  - Fences with only characters (no trailing text) remain unchanged
  - Fences with trailing whitespace only are NOT stripped
  - Mixed tilde/backtick lines are NOT modified (the mixed-fence guard catches them)
  - Mid-line fence character sequences are NOT modified (the line-start anchor `^` prevents this)
- **Location:** Replace the body of `_FencePreProcessor.process()` in `parser_infrastructure.py` (currently `return content` on line ~20).

**File 2: `src/teddy_executor/core/services/markdown_plan_parser.py`**
- In `_parse_actions`, after the main `while stream.has_next()` loop that consumes actions, add a tail-end loop that silently consumes any remaining `BlockCode` or `CodeFence` nodes.
- **Location:** After line ~230 (end of the main `while stream.has_next()` block) and before `return actions` on line ~234.
- **Pattern** (consistent with 02-06's between-action skip):
  ```python
  # Tail-end resilience: silently consume trailing code blocks
  from mistletoe.block_token import BlockCode, CodeFence
  while stream.has_next() and isinstance(stream.peek(), (BlockCode, CodeFence)):
      stream.next()
  ```
- **Critical Constraint:** Do NOT consume `Paragraph` nodes at the tail end — trailing Paragraph nodes must still raise a validation error per the slice's edge cases.

### Test Strategy (Test Harness Triad)
- **Driver**: Use `MarkdownPlanBuilder` for constructing valid plans, then append trailing artifacts via raw string manipulation.
- **Observer**: Use standard `pytest` assertions on the parsed `Plan` object (action count, action content, content correctness).
- **Setup**: Standard `parser` fixture from `conftest.py` resolving `IPlanParser`.
- **Key Assertions from Prototype:**
  - `"~~~~~~ trailing text"` → `"~~~~~~"` (6-tilde closing fence stripped)
  - `"`````` trailing text"` → `"``````"` (6-backtick closing fence stripped)
  - `"~~~~ trailing text"` → `"~~~~ trailing text"` (4-tilde fence NOT stripped — below threshold)
  - `"~~~~~~python"` → `"~~~~~~"` (adjacent trailing text stripped)
  - `"    ~~~~~~ trailing text"` → `"    ~~~~~~"` (indentation preserved)
  - `"~~~~~~\` trailing"` → `"~~~~~~\` trailing"` (mixed fence chars preserved — guard prevents stripping)
  - Trailing `CodeFence`/`BlockCode` after last action → silently skipped, correct actions returned
  - Clean plan (no artifacts) → unchanged after preprocessing
