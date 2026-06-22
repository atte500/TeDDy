# Bug: Filepath Parsing Double Underscore

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

When a plan action (e.g., `READ`) references a filepath that contains double underscores (e.g., `src/teddy_executor/__main__.py`), the path is incorrectly normalized to `src/teddy_executor/main.py` (leading underscores stripped). This causes the file lookup to fail with "File to read does not exist" because the actual file is named with double underscores.

**Expected:** `src/teddy_executor/__main__.py` is resolved as `src/teddy_executor/__main__.py`.
**Actual:** `src/teddy_executor/__main__.py` is resolved as `src/teddy_executor/main.py`.

**Minimal Reproduction:**
1. Provide a plan containing `READ` action with resource path `src/teddy_executor/__main__.py`.
2. The parser normalizes the path to `src/teddy_executor/main.py`.
3. File system lookup fails.

## Context & Scope

### Regressing Delta
Unknown yet. The bug is present in the current workspace. The issue likely lies in path normalization logic within the plan parser or utilities that process file paths from plan actions.

### Environmental Triggers
No specific OS or environment conditions required. Any plan action with a path containing double underscores triggers the bug.

### Ruled Out
_Nothing ruled out yet._

## Diagnostic Analysis

### Causal Model
Mistletoe (the Markdown parser) interprets `__main__` as `<strong>main</strong>` because double underscores are Markdown emphasis syntax. The AST represents this as a `Strong` token containing a `RawText` node with only `"main"`. The delimiter underscores are consumed and not stored.

The `get_child_text` function extracts text from AST nodes. Previously, it skipped `Strong`/`Emphasis` tokens entirely. Adding traversal recovers the inner text (`main`) but NOT the underscore delimiters. To preserve literal double underscores, the function would need to:
- (A) Emit delimiters for `Strong` (`__text__`) and `Emphasis` (`_text_`). However, this would corrupt actual bold/italic formatting (e.g., `**bold**` → `__bold__` or `**bold**` depending on delimiter choice).
- (B) Bypass the parsed AST for resource extraction fallback and use raw Markdown source with regex extraction. This is safer but requires changes in `parser_metadata.py` rather than `get_child_text`.

**Current impact:**
1. **Link-formatted paths** (`[text](target)`) work correctly for resource extraction because `_process_link_key` uses `Link.target` which retains underscores. Descriptions and error messages show mangled text (cosmetic).
2. **Plain-text paths** (no link) fall back to `get_child_text` and lose underscores entirely, causing functional failure (file not found).
3. The MRP protocol mandates link format, but the fallback remains vulnerable.

### Discrepancies
- Path `__main__.py` becomes `main.py` in `get_child_text` output but is correctly preserved in link target. (Investigative finding, not a direct bug symptom – resolved: The primary `READ` action using link format succeeds; `get_child_text` is used for descriptions and error formatting)
- `Description` field shows "Read the main.py file." instead of "Read the __main__.py file." (Cosmetic – unresolved. Requires either emitting delimiters in `get_child_text` or extracting raw source for descriptions.)
- Plain-text path extraction (no Markdown link) falls back to `get_child_text`, losing underscores and causing functional failure. (Functional – unresolved. MRP standard requires link format, but unprotected.)
- Shadow file fix attempt (added `Strong`/`Emphasis` traversal) did NOT restore underscore delimiters because the AST only stores inner text. (Resolved: Adding traversal is insufficient; the fix must come at a different layer.)

### Investigation History
1. _Initial report._ A `READ` action with path `src/teddy_executor/__main__.py` was provided in a plan. The execution report showed it tried to read `src/teddy_executor/main.py` instead. _Conclusion:_ Path normalization appears to be stripping underscores, but subsequent investigation shows the link target is correctly preserved. The initial error may have been from an older parser code path or a plain-text format (no link).

2. _Mistletoe AST probe._ Parsed the plan with raw mistletoe and printed the AST. The link target (`/src/teddy_executor/__main__.py`) is correct, but the link children show `Strong` tokens wrapping `"main"` because mistletoe interprets `__main__` as emphasis. _Conclusion:_ The bug is in `get_child_text` which does not traverse `Strong`/`Emphasis` spans.

3. _get_child_text empirical probe._ Called `get_child_text` on the list item and link node. It returned `"Resource: src/teddy_executor/main.py"` and displayed text `"src/teddy_executor/main.py"`, confirming underscores are stripped by `get_child_text`. _Conclusion:_ `get_child_text` must be fixed to recursively include emphasis span content.

4. _Shadow file verification attempt._ Created a shadow version of `get_child_text` that recurses into `Strong` and `Emphasis` tokens. The fix recovered the inner text (`main`) but NOT the underscore delimiters (`__`), because `Strong` tokens only contain the non-delimiter text (`main`). The double underscore markers are consumed by mistletoe's Markdown parser and are not represented in the AST. _Conclusion:_ Simply traversing `Strong`/`Emphasis` is insufficient. To reconstruct the original literal text, we would need either: (a) emit emphasis delimiters when encountering `Strong`/`Emphasis` tokens (risks corrupting actual formatting), or (b) bypass the parsed AST entirely for resource extraction fallback and use raw Markdown source.

## Solution

### Root Cause
Mistletoe (the Markdown parser) interprets `__text__` as `<strong>text</strong>`, storing only the inner content `"text"` in a `Strong` AST token. The `get_child_text` function extracts text from AST nodes without traversing `Strong`/`Emphasis` tokens, so double underscores are lost when extracting plain-text values from list items.

### Fix (Scoped to `_process_text_key` in `parser_metadata.py`)
Instead of calling `get_child_text(item)` to extract the full text and then parsing the value from the colon-delimited text, we pass the raw AST node to `_process_text_key`. The function now traverses the node's children directly, emitting `__..__` for `Strong` tokens and `_.._` for `Emphasis` tokens when extracting the value after the colon. This scopes the fix to:

- **Text-based metadata keys** (plain-text `Resource:`, `Lines:`, `Overwrite:`) – now correctly preserve double underscores.
- **Description extraction** – unaffected (uses separate code path in `parse_action_metadata`).
- **Link-based resource extraction** – already works correctly via `Link.target`, unaffected.
- **Error formatting** – cosmetic only, left as-is.

**Trade-off:** If a metadata value (e.g., a plain-text file path) contains text that mistletoe parses as bold (e.g., `**bold**`), it will be emitted as `__bold__`. Both are semantically equivalent Markdown for `<strong>`, and metadata values are used programmatically (file paths, line numbers), not rendered as Markdown. This is acceptable.

### Preventative Measures
- The fix is isolated to `_process_text_key`, ensuring no side effects on description extraction, link parsing, or error formatting.
- The primary resource extraction (via `Link.target`) already works correctly and is unaffected.
- No changes were made to `get_child_text` in `parser_infrastructure.py`, preserving backward compatibility for all other callers.
