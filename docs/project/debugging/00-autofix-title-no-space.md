# Bug: Autofix markdown title missing space after `#`
- **Status:** Resolved (complete: heading normalization + preamble stripping + file write-back)
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** [docs/project/specs/plan-format.md](/docs/project/specs/plan-format.md)

## Symptoms

**Expected:** The parser should handle `#Title` (missing space after `#`) as a valid H1 heading by treating it as equivalent to `# Title`.

**Actual:** When a plan starts with `#Title` instead of `# Title`, the parser either fails to parse it as a heading (treating it as plain text or throwing a validation error) or the title extraction fails.

**Minimal Reproduction Steps:**
1. Create a plan file with `#My Plan Title` as the first line (missing space after `#`)
2. Run the `MarkdownPlanParser` to parse it
3. Observe that parsing fails or title is empty/incorrect

## Context & Scope

### Regressing Delta
N/A - This is a feature gap, not a regression. The parser needs resilience against this common formatting error.

### Environmental Triggers
N/A - Pure parsing behavior, no platform-specific conditions.

### Ruled Out
- (Nothing yet)

## Diagnostic Analysis

### Causal Model
The `MarkdownPlanParser` uses two distinct mechanisms for H1 heading detection:
1. `strip_preamble` via regex `r"(?:^|\n)# (?!#)"` — requires a space after `#` (strict `# ` pattern). `#Title` does NOT match.
2. `_parse_strict_top_level` uses the mistletoe AST where `#Title` (no space) is NOT parsed as a `Heading` token by CommonMark — mistletoe treats it as a `Paragraph` or raw text.

When a plan starts with `#Title\n`, the preamble stripping regex fails to find an H1, leaving the entire content (including `#Title`) as the preamble. This causes the ast stream to begin with non-heading tokens, leading to structural mismatch errors in `_parse_strict_top_level` or title extraction returning empty/none.

### Discrepancies
[To be filled as discrepancies are found]

### Investigation History
1. Created Case File and initial MRE. MRE produced AttributeError: 'Plan' object has no attribute 'status'. This was because MRE accessed `result.status` which does not exist on the `Plan` model. Fixed MRE to not access .status.
2. Created shadow parser files with heading normalization fix. Attempted to run MRE but got `ModuleNotFoundError: No module named 'spikes'` because `sys.path` did not include the project root. Fixed import path by adding project root to sys.path.
3. Attempted to run MRE after import path fix but got NameError: name 'Any' is not defined in shadow_markdown_plan_parser.py. Fixed by adding `Any` and `List` to typing imports.
4. Fixed MRE import path and reran. MRE failed with `ModuleNotFoundError: No module named 'spikes'` due to duplicate sys.path entries and sys execution order. Fixed by adding `os.path.dirname(os.path.dirname(_script_dir))` to sys.path before import.
5. Ran MRE after import fix. Successfully verified:
   - Production parser FAILS on `#Title` (no space)
   - Production parser PASSES on `# Title` (with space)
   - Shadow parser (with heading normalization) PASSES on both `#Title` and `# Title`
   - **BUG CONFIRMED: Production parser fails on '#Title' / FIX VERIFIED: Shadow parser handles '#Title' correctly**
6. Alignment phase: Presented RCA to user. User raised valid concern about code fence overreach. Proposed code-fence-aware normalization. User suggested simpler approach: only normalize first line (the H1 title). Confirmed approach is safe because no code fences, shebangs, or other content can appear on the first line of a plan. User approved with additional requirement: "the resulting plan.md file should also be corrected not show original wrong title". This is satisfied because the normalized content is stored as `Plan.raw_content`.
7. Systemic Audit: Searched codebase for other heading-dependent patterns (strip_preamble regex, H1 detection in validators). Found that `strip_preamble` regex `r"(?:^|\n)# (?!#)"` at `markdown_plan_parser.py:78` is the only raw-text heading detection. Normalization runs before this regex, so `#Title` becomes `# Title` and matches correctly. No other code paths independently parse `# ` at line start.
8. Extended Scope – File Write-Back & Preamble Stripping: User requested the `plan.md` file on disk be overwritten with corrected content (normalized heading + stripped preamble). Implemented via `Path.write_text` in the parser's `parse()` method, guarded by `plan_path` and `is_session`. The preamble stripping regex was changed from `r"(?:^|\n)# (?!#)"` to `r"^[ \t]*#"` with `re.MULTILINE` to handle leading whitespace and `#Title` without space. Write-back is idempotent: compares `current_disk.rstrip()` with `clean_content` to avoid unnecessary writes. All tests pass: 9/9 regression, 916/3 full suite. Final commit made.

### Discrepancies
- **Discrepancy 1**: The `normalize_headings` regex could modify content inside code fences (e.g., shebangs, Python comments). This was raised by the user during alignment. **(Resolved: We switched to first-line-only normalization, which is outside any code fences by definition since the plan's H1 title is always the first line.)**
- **Discrepancy 2**: The normalized `raw_content` stored in the Plan object will differ from the original plan file on disk. The user requested "the resulting plan.md file should also be corrected not show original wrong title". **(Resolved: The write‑back now overwrites the original `plan.md` file with the corrected content after successful parsing, ensuring the file on disk is always consistent with the in-memory representation.)**
- **Discrepancy 3**: The preamble (text before the first `# heading`) is currently stripped from `raw_content`, but the file on disk still contains it. The user wants the preamble removed from the saved file. **(Resolved: The write‑back uses `raw_content` which already has preamble stripped, so the saved file will no longer contain preamble.)**

## Solution

### Root Cause
The **CommonMark specification** (used by the `mistletoe` library) strictly requires a space after `#` to interpret text as an ATX heading. When a plan starts with `#Title` (missing space), mistletoe parses it as a **Paragraph**, not a `Heading(level=1)`. Additionally, the original preamble stripping regex `r"(?:^|\n)# (?!#)"` required a space after `#`, so `#Title` did NOT match, causing preamble stripping to fail or skip the heading line.

### The Fix (Three Parts)

#### Part 1: Heading Normalization
Added `normalize_headings()` in `parser_infrastructure.py` that inserts a space after `#` on the **first line only** before parsing. This is safe because code fences cannot appear on the first line.

#### Part 2: Preamble Stripping (Relaxed Regex)
Changed the preamble stripping regex from `r"(?:^|\n)# (?!#)"` to `r"^[ \t]*#"` with `re.MULTILINE` to match any line starting with `#` (including `#Title` without space, and with leading whitespace). Normalization is called **after** preamble stripping so it always targets the heading line.

#### Part 3: File Write-Back
After successful parsing, the corrected content (normalized heading + stripped preamble) is written back to the source file for **session plans** (plan_path contains `.teddy/sessions/`). The write is idempotent: it compares `current_disk.rstrip()` with `clean_content` to avoid unnecessary writes.

### Files Changed
| File | Change |
|---|---|
| `src/teddy_executor/core/services/parser_infrastructure.py` | Added `normalize_headings()` function |
| `src/teddy_executor/core/services/markdown_plan_parser.py` | Added heading normalization call, relaxed preamble stripping regex, added file write-back logic |
| `tests/suites/unit/core/services/test_bug_00_normalize_h1.py` | Added regression tests: 5 unit + 2 integration (heading normalization) + 2 integration (file write-back and idempotency) |
| `docs/project/debugging/00-autofix-title-no-space.md` | Case File (this document) |

### Preventative Measures
- This class of bug (parser failing on semantically valid but syntactically malformed input) is mitigated by adding a pre-processing normalization layer before the strict parser.
- The preamble stripping regex now accepts any `#` at line start, making it robust to `#Title` without space and leading whitespace.
- File write‑back ensures the user's `plan.md` on disk is always consistent with the corrected in-memory representation.
- Regression tests (9 total) cover heading normalization, preamble stripping, file write‑back, and idempotency.

### Root Cause
The **CommonMark specification** (used by the `mistletoe` library) strictly requires a space after `#` to interpret text as an ATX heading. When a plan starts with `#Title` (missing space), mistletoe parses it as a **Paragraph**, not a `Heading(level=1)`. The `strip_preamble` regex `r"(?:^|\n)# (?!#)"` also requires a space after `#`, so `#Title` does NOT match. This causes the entire content (including `#Title`) to be treated as preamble, leading to a structural mismatch error in `_parse_strict_top_level` (expected `Heading(level=1)` but found `Paragraph`).

### The Fix
Add a **pre-processing step** that inserts a space after `#` on the **first line only** before any parsing occurs. This is safe because:
- The first line of a valid plan is always the H1 title.
- No code fences, shebangs, or other content can appear on the first line.
- The normalized content is stored as `raw_content` in the `Plan` object, ensuring downstream consumers see the corrected title.

#### Implementation Details
1. **New function** in `parser_infrastructure.py`:
```python
def normalize_headings(content: str) -> str:
    """Insert a space after `#` if missing on the first line (the H1 title)."""
    first_newline = content.find("\n")
    if first_newline == -1:
        first_line = content
        rest = ""
    else:
        first_line = content[:first_newline]
        rest = content[first_newline:]
    if re.match(r"^#[^ #\t\n]", first_line):
        first_line = "# " + first_line[1:]
    return first_line + rest
```

2. **One call** in `MarkdownPlanParser.parse()` at the beginning, after `.rstrip()` and before the preamble stripping:
```python
clean_content = normalize_headings(clean_content)
```

3. **Import** `normalize_headings` from `parser_infrastructure` in `markdown_plan_parser.py`.

### Preventative Measures
- This class of bug (parser failing on semantically valid but syntactically malformed input) is mitigated by adding a pre-processing normalization layer before the strict parser. Future formatting issues (e.g., `##` without space, `###` without space) could also be caught by extending `normalize_headings` to handle all heading levels.
- A regression test has been added to ensure this fix persists.
- No systemic audit found other code paths that independently parse `# ` patterns — all heading detection routes through the same entry point (`MarkdownPlanParser.parse`), making the single normalization point effective.
