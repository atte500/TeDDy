# Task: Fix Message Content Blank Lines by Replacing Blind double_newlines with Raw Text Extraction

## Business Goal
Replace the harmful `double_newlines()` transformation (which blindly doubled all single newlines, breaking tables/lists/code blocks) with raw text extraction that preserves the LLM's original formatting exactly.

## Root Cause
The LLM outputs proper Markdown with blank lines between paragraphs. However, `parse_message_action()` in `action_parser_complex.py` rendered each AST child node individually using `MarkdownRenderer` and joined them with an empty string `""`. This lost blank lines between block-level elements:

```
LLM writes:  "Para1.\n\nPara2.\n\n- List items"
Reconstructed: "Para1.\nPara2.\n- List items"  (blank lines lost!)
```

The `double_newlines()` function was a band-aid that tried to compensate by doubling every `\n`. This was too aggressive and broke tables, lists, and code blocks.

## Fix
Replace the lossy AST-rendering approach with raw text extraction. Mistletoe tokens expose a `line_number` attribute (1-indexed start line). When parsing a `## Message` section, we extract all text from that heading's line onward directly from the original plan content, preserving every newline exactly as the LLM wrote them.

### Changes Made

#### 1. action_parser_complex.py
- Modified `parse_message_action()` to accept an optional `raw_content` parameter.
- If `raw_content` is provided, use it directly (preserving blank lines).
- Fall back to legacy MarkdownRenderer for backwards compatibility.

#### 2. markdown_plan_parser.py
- In `parse()`, when a `## Message` section is detected, extract raw content from `clean_content` using the heading's `line_number`.
- Pass `raw_content` to `parse_message_action()`.

#### 3. action_factory.py
- Removed `double_newlines` import and call from `_handle_message_protocol()`.
- Message content now passes through as-is.

#### 4. string.py
- Removed `double_newlines()` function entirely. It was harmful and no longer used in production.

## Verification
1. Run `poetry run pytest` – all tests pass.
2. Tables, lists, and code blocks in agent messages display correctly (internal `\n` preserved).
3. Paragraphs separated by blank lines in agent messages display with correct spacing.
4. `double_newlines` no longer referenced anywhere in production code or tests.
