# Bug: Research Snippet Spacing & Hint Polish

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)

## Symptoms
1. Research snippets still contain mashed words like `explicitmemorymanagement`, `ofMemoryManagement`, `StackvsHeap`, and `Heapmanagementis`.
2. The "READ hint" in the execution report appears before the results and says "below", which is suboptimal if results are long.

## Context & Scope
### Regressing Delta
Current implementation in `WebSearcherAdapter` only handles `.` and `,` followed by a non-space.
Template `execution_report.md.j2` places the hint before the loop.

### Environmental Triggers
DuckDuckGo search snippets containing artifacts from tag stripping (likely bolded terms mashed with surrounding text).

### Ruled Out
- `WebScraperAdapter`: Unrelated to search snippets.

## Diagnostic Analysis
### Causal Model
The `WebSearcherAdapter` performs a single, limited regex pass on snippets. Mashed words occur when:
- Case transitions (lower -> Upper) are not handled.
- Extended punctuation (`:`, `!`, `?`) is not handled.
- Digits mashed with letters are not handled.
- All-lowercase mashes (e.g. `explicitmemorymanagement`) are likely due to missing spaces in the source snippet provided by the API, which are hard to fix without NLP/Dictionary but might be mitigated by checking common patterns.

### Discrepancies
- None yet.

### Investigation History
1. Initial fix implemented for basic punctuation.
2. User identified remaining mashes in CamelCase and complex punctuation scenarios.
3. Spike 01: Confirmed `lowerUpper` regex fixes CamelCase mashes (`ofMemory`).
4. Spike 02: Attempted glue-word heuristics; rejected due to false positives (e.g., "Missing" -> "M is sing").
5. Spike 03: Probing `ddgs` raw output to isolate root cause of remaining mashes.
6. Investigation: Isolated structural root cause to `BaseSearchEngine.extract_results` in `ddgs` library (joins text nodes with empty string).
7. Implementation: Applied a structural monkeypatch to `BaseSearchEngine.extract_results` to join nodes with spaces, and restored a minimal punctuation-spacing regex.
8. Polish: Moved report hint to end of section and updated wording to "above".
