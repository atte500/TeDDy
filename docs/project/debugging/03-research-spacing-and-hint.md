# Bug: Research Snippet Spacing & Hint

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../../milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
1. `RESEARCH` action results (snippets) contain text where spaces appear to be removed or compressed incorrectly.
2. Lack of explicit instruction/hint in the research output suggesting that the user (or AI agent) should use the `READ` action to inspect the full content of provided source URLs.

## Context & Scope
### Regressing Delta
- **Unknown:** Need to determine if this is a recent regression or a long-standing issue in `WebSearcherAdapter`.

### Environmental Triggers
- **OS:** Platform-agnostic (likely).
- **Dependency:** `ddgs` (DuckDuckGo Search) library versioning might be relevant.

### Ruled Out
- TBD

## Diagnostic Analysis
### Causal Model
TBD - Analyzing how `WebSearcherAdapter` processes `ddgs` results.

### Discrepancies
- TBD

### Investigation History
1. Initializing Case File and gathering implementation context.
2. Creating MRE `debug/repro_research_spacing.py` to isolate where spacing is lost.
3. Observed that `WebSearcherAdapter` preserves spaces provided by the search library.
4. Fixing MRE to use dictionary structure to avoid Jinja2/Serialization errors.
5. Implemented `clean_snippet` in `WebSearcherAdapter` and added `READ` hint to Jinja2 template.
6. Suppressed raw `query_results` in the execution report to prevent redundant detail output.

## Solution
### Implemented Fixes
- Added `clean_snippet` logic to `WebSearcherAdapter` using regex to fix missing spaces after punctuation (e.g., `.` or `,` followed by a character).
- Updated `execution_report.md.j2` to include a simplified `READ` hint in the `RESEARCH` action output.
- Modified `execution_report.md.j2` to suppress the redundant raw `query_results` dictionary in the action details section for successful searches.

### Prevention
- Added `test_search_cleans_snippet_spacing` to `tests/suites/integration/adapters/outbound/test_web_searcher_adapter.py`.
- Added `test_research_report_includes_hint_and_hides_raw_details` to `tests/suites/integration/core/services/test_report_formats_integration.py`.
